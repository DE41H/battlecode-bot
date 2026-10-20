// Native C++ port of the v2 strategy. Map masks, occupancy, distance searches, and
// hypothetical vision are handled by cambc's inbuilt C++ API.
#include <cambc.h>
#include "bot.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <functional>
#include <limits>
#include <optional>
#include <span>
#include <tuple>
#include <utility>
#include <variant>
#include <vector>

using cambc::bitboard;
using cambc::champion;
using cambc::camp;
using cambc::team;
using cambc::vec2;

constexpr int claim_slots = 8;
constexpr float bank_gems = 60.0f;
constexpr float near_altar = 5.0f;
constexpr float low_health = 0.35f;
constexpr float linked_low_health = 0.5f;
constexpr float healed_health = 0.9f;
constexpr float fight_edge = 0.8f;
constexpr float retreat_edge = 0.9f;
constexpr float press_edge = 0.5f;
constexpr int contest_turns = 4;
constexpr int contest_backoff = 30;
constexpr int shop_gold = 150;
constexpr int candidates = 3;
constexpr int ambush_backoff = 10;
// Fuel gates for the C++ turn budget of 100k. The refine search covers the whole map (up to ~45k on
// big-world), so it needs room to finish. The ward scan starts at ward_fuel and stops at ward_reserve.
constexpr std::uint64_t refine_fuel = 60'000;
constexpr std::uint64_t replan_fuel = 60'000;
constexpr std::uint64_t ward_fuel = 30'000;
constexpr std::uint64_t ward_reserve = 12'000;

int distance(vec2 a, vec2 b) {
    return static_cast<int>(a.chebyshev_distance(b));
}

bitboard tiles_around(vec2 position, int radius) {
    bitboard result;
    result.draw_chebyshev(position, static_cast<float>(radius));
    return result;
}

bool alive(const cambc::unit& unit) {
    try {
        return unit.is_visible() && unit.health() > 0;
    } catch (const cambc::error&) {
        return false;
    }
}

std::uint32_t champion_id(const champion& value) {
    return static_cast<std::uint32_t>(static_cast<cambc::handle_champion_t>(value));
}

int draft_pick(cambc::champion_type type) {
    switch (type) {
    case cambc::champion_type::ryth: return static_cast<int>(cambc::champion_draft::ryth);
    case cambc::champion_type::vesper_vale: return static_cast<int>(cambc::champion_draft::vesper_vale);
    case cambc::champion_type::vendetta: return static_cast<int>(cambc::champion_draft::vendetta);
    case cambc::champion_type::cassi:
    case cambc::champion_type::issac: return static_cast<int>(cambc::champion_draft::cassi_and_issac);
    case cambc::champion_type::stellar: return static_cast<int>(cambc::champion_draft::stellar);
    case cambc::champion_type::prism: return static_cast<int>(cambc::champion_draft::prism);
    case cambc::champion_type::marcella: return static_cast<int>(cambc::champion_draft::marcella);
    case cambc::champion_type::willow: return static_cast<int>(cambc::champion_draft::willow);
    case cambc::champion_type::ren: return static_cast<int>(cambc::champion_draft::ren);
    case cambc::champion_type::varg: return static_cast<int>(cambc::champion_draft::varg);
    case cambc::champion_type::tavi: return static_cast<int>(cambc::champion_draft::tavi);
    default: return -1;
    }
}

std::vector<int> draft_plan() {
    std::vector<int> result;
    const cambc::draft_memory_buffer memory;
    if (memory.size() < 3 || std::to_integer<std::uint8_t>(memory[0]) != 1)
        return result;
    const auto count = std::to_integer<std::uint8_t>(memory[1]);
    if (memory.size() < static_cast<std::size_t>(count) + 3)
        return result;
    result.reserve(count);
    for (std::size_t i = 0; i < count; ++i)
        result.push_back(std::to_integer<std::uint8_t>(memory[i + 2]));
    return result;
}

void read_claims(std::array<int, claim_slots>& claims) {
    std::array<std::uint8_t, claim_slots> data{};
    cambc::shared_memory.read(0, std::span{data});
    for (std::size_t i = 0; i < data.size(); ++i)
        claims[i] = data[i] ? static_cast<int>(data[i]) - 1 : -1;
}

void write_claim(int slot, int group) {
    if (slot < 0 || slot >= claim_slots)
        return;
    cambc::shared_memory[static_cast<std::size_t>(slot)] =
        static_cast<std::uint8_t>(group < 0 ? 0 : group + 1);
}

struct GroupInfo {
    cambc::map::camp_group group;
    bitboard tiles;
    std::vector<vec2> positions;
    int index = 0;
    int gems = 0;
    int gold = 0;
    int respawn = 0;
    float max_health = 0;
    float strength = 0;
    int cx = 0;
    int cy = 0;
    int radius = 0;
    vec2 anchor{};
    float altar_distance = 0;
    float spawn_distance = 0;
    bool reachable = false;

    explicit GroupInfo(cambc::map::camp_group value) : group(std::move(value)) {}
};

struct ScoringEntry {
    int index;
    int cx;
    int cy;
    float early_value;
    float late_value;
    float trip_cost;
    float fixed;
    float strength;
};

class Knowledge {
public:
    std::vector<GroupInfo> groups;
    bitboard ally_spawn;
    bitboard enemy_spawn;
    bitboard terrain;
    bitboard bushes;
    bitboard walls;
    bitboard spawn_tiles;
    bitboard armed;
    bitboard enemy_half;
    std::vector<vec2> all_altars;
    std::vector<vec2> altars;
    std::vector<bitboard> altar_spots;
    std::vector<std::vector<int>> altar_gates;
    std::vector<bool> locked;
    std::vector<int> group_at;
    std::vector<std::uint32_t> available;
    std::vector<bool> reward_ready;
    std::vector<float> remaining;
    std::vector<std::uint32_t> avoid;
    std::vector<ScoringEntry> scoring;
    std::vector<std::tuple<camp, int, float>> seen;
    std::vector<std::pair<int, bitboard>> collateral_cache;
    std::vector<std::pair<int, bitboard>> armed_cache;
    int capture_time = cambc::constants::capture_time;

    Knowledge() : ally_spawn(cambc::map::spawn_region(team::ally)),
                  enemy_spawn(cambc::map::spawn_region(team::enemy)),
                  walls(cambc::map::walls()), bushes(cambc::map::bushes()) {
        terrain = cambc::map::walls() | cambc::map::holes()
            | cambc::map::altars() | enemy_spawn;
        bitboard reachable;
        cambc::distance_field spawn_field;
        spawn_field.compute(terrain, ally_spawn, reachable);

        const auto map_groups = cambc::map::camp_groups();
        groups.reserve(map_groups.size());
        group_at.assign(static_cast<std::size_t>(cambc::map::width() * cambc::map::height()), -1);
        spawn_tiles.clear();
        armed.clear();
        for (std::size_t i = 0; i < map_groups.size(); ++i) {
            GroupInfo info{map_groups[i]};
            info.index = static_cast<int>(i);
            info.gems = static_cast<int>(info.group.gem_value());
            info.gold = static_cast<int>(info.group.gold_value());
            info.respawn = info.group.max_respawn_timer();
            info.tiles = info.group.spawn_tiles();
            info.positions = info.tiles.positions();
            for (const auto& member : info.group.camps()) {
                const auto base = member.base_stats();
                info.max_health += static_cast<float>(base.base_health);
                info.strength += static_cast<float>(base.base_strength);
            }
            for (const auto position : info.positions) {
                const auto key = static_cast<std::size_t>(position.y * cambc::map::width() + position.x);
                group_at[key] = info.index;
            }
            if (info.positions.empty())
                continue;
            int sx = 0, sy = 0;
            for (const auto p : info.positions) {
                sx += p.x;
                sy += p.y;
            }
            info.cx = sx / static_cast<int>(info.positions.size());
            info.cy = sy / static_cast<int>(info.positions.size());
            info.anchor = info.positions.front();
            info.radius = 0;
            for (const auto p : info.positions) {
                const int d = std::max(std::abs(p.x - info.cx), std::abs(p.y - info.cy));
                info.radius = std::max(info.radius, d);
                if (d < std::max(std::abs(info.anchor.x - info.cx), std::abs(info.anchor.y - info.cy)))
                    info.anchor = p;
            }
            info.reachable = !(info.tiles & reachable).is_empty();
            spawn_tiles |= info.tiles;
            if (info.strength > 0)
                armed |= info.tiles;
            groups.push_back(std::move(info));
        }

        all_altars = cambc::map::altars().positions();
        for (const auto altar : all_altars) {
            auto ring = tiles_around(altar, cambc::constants::submit_gems_range);
            auto spots = ring & reachable;
            if (spots.is_empty())
                continue;
            std::vector<int> gates;
            auto open_spots = spots;
            for (const auto& info : groups) {
                if (!(spots & info.tiles).is_empty()) {
                    gates.push_back(info.index);
                    open_spots &= ~info.tiles;
                }
            }
            altars.push_back(altar);
            altar_spots.push_back(spots);
            altar_gates.push_back(open_spots.is_empty() ? gates : std::vector<int>{});
        }
        if (altars.empty()) {
            altars = all_altars;
            altar_spots.resize(altars.size());
            altar_gates.resize(altars.size());
        }
        locked.resize(altars.size(), false);

        const auto ally_tiles = ally_spawn.positions();
        const auto enemy_tiles = enemy_spawn.positions();
        vec2 spawn_center{}, enemy_center{};
        for (const auto p : ally_tiles) {
            spawn_center.x += p.x;
            spawn_center.y += p.y;
        }
        for (const auto p : enemy_tiles) {
            enemy_center.x += p.x;
            enemy_center.y += p.y;
        }
        if (!ally_tiles.empty()) {
            spawn_center.x /= static_cast<int>(ally_tiles.size());
            spawn_center.y /= static_cast<int>(ally_tiles.size());
        }
        if (!enemy_tiles.empty()) {
            enemy_center.x /= static_cast<int>(enemy_tiles.size());
            enemy_center.y /= static_cast<int>(enemy_tiles.size());
        }
        for (auto& info : groups) {
            info.altar_distance = nearest_altar_distance_xy(info.cx, info.cy);
            info.spawn_distance = static_cast<float>(
                std::max(std::abs(info.cx - spawn_center.x), std::abs(info.cy - spawn_center.y)));
        }

        enemy_half.clear();
        const int max_dimension = std::max(cambc::map::width(), cambc::map::height());
        for (int d = 0; d < max_dimension; ++d) {
            auto theirs = tiles_around(enemy_center, d);
            auto ours = tiles_around(spawn_center, d);
            enemy_half |= theirs & ~ours;
        }

        available.resize(groups.size(), 0);
        reward_ready.resize(groups.size(), false);
        remaining.reserve(groups.size());
        avoid.resize(groups.size(), 0);
        for (const auto& info : groups)
            remaining.push_back(info.max_health);
        for (const auto& info : groups) {
            if (!info.reachable)
                continue;
            scoring.push_back({info.index, info.cx, info.cy,
                static_cast<float>(info.gems) + 0.35f * info.gold,
                info.gems > 0 ? static_cast<float>(info.gems) + 0.1f * info.gold : 0.0f,
                2.5f * info.spawn_distance + cambc::constants::recall_time,
                0.4f * info.altar_distance + 1.0f, info.strength});
        }
    }

    float nearest_altar_distance_xy(int x, int y) const {
        if (altars.empty())
            return 999.0f;
        int best = std::numeric_limits<int>::max();
        for (const auto altar : altars)
            best = std::min(best, std::max(std::abs(x - altar.x), std::abs(y - altar.y)));
        return static_cast<float>(best);
    }

    float nearest_altar_distance(vec2 position) const {
        return nearest_altar_distance_xy(position.x, position.y);
    }

    void observe() {
        const auto now = cambc::round_number();
        seen.clear();
        std::vector<float> health(groups.size(), 0.0f);
        for (const auto& visible_camp : cambc::vision::camps()) {
            const auto spawn = visible_camp.spawn_position();
            const auto key = static_cast<std::size_t>(spawn.y * cambc::map::width() + spawn.x);
            const int index = key < group_at.size() ? group_at[key] : -1;
            if (index < 0)
                continue;
            const auto hp = visible_camp.health();
            seen.emplace_back(visible_camp, index, hp);
            if (hp > 0)
                health[static_cast<std::size_t>(index)] += hp;
        }
        const auto me = cambc::self().position();
        std::vector<int> nearby;
        for (const auto& info : groups)
            if (std::max(std::abs(info.cx - me.x), std::abs(info.cy - me.y)) - info.radius <= 8)
                nearby.push_back(info.index);
        if (nearby.empty())
            return;
        const auto visible = cambc::vision::visible_tiles();
        for (const int index : nearby) {
            auto& info = groups[static_cast<std::size_t>(index)];
            if ((info.tiles & visible).is_empty())
                continue;
            // A living camp in view means the group is alive; state() re-reads vision, so skip it then.
            if (health[index] > 0) {
                available[index] = now;
                reward_ready[index] = false;
                remaining[index] = health[index];
                continue;
            }
            try {
                const auto state = info.group.state();
                if (const auto* respawning = std::get_if<cambc::map::camp_group_respawning>(&state)) {
                    available[index] = now + static_cast<std::uint32_t>(respawning->timer);
                    reward_ready[index] = false;
                    remaining[index] = info.max_health;
                } else if (std::holds_alternative<cambc::map::camp_group_reward_available>(state)) {
                    available[index] = now;
                    reward_ready[index] = true;
                    remaining[index] = 0.0f;
                } else {
                    available[index] = now;
                    reward_ready[index] = false;
                }
            } catch (const cambc::error&) {
            }
        }
    }

    bool gate_alive(int index) const {
        return available[static_cast<std::size_t>(index)] <= cambc::round_number()
            && !reward_ready[static_cast<std::size_t>(index)];
    }

    std::vector<int> open_altars() const {
        std::vector<int> result;
        for (std::size_t i = 0; i < altar_gates.size(); ++i) {
            bool blocked = false;
            for (const int gate : altar_gates[i])
                if (gate_alive(gate)) {
                    blocked = true;
                    break;
                }
            if (!blocked)
                result.push_back(static_cast<int>(i));
        }
        return result;
    }

    void captured(int index) {
        const auto& info = groups[static_cast<std::size_t>(index)];
        available[static_cast<std::size_t>(index)] =
            cambc::round_number() + static_cast<std::uint32_t>(info.respawn);
        reward_ready[static_cast<std::size_t>(index)] = false;
        remaining[static_cast<std::size_t>(index)] = info.max_health;
    }

    const bitboard& collateral(int index) {
        for (const auto& entry : collateral_cache)
            if (entry.first == index)
                return entry.second;
        collateral_cache.emplace_back(index, armed & ~groups[static_cast<std::size_t>(index)].tiles);
        return collateral_cache.back().second;
    }

    const bitboard& armed_within(int radius) {
        for (const auto& entry : armed_cache)
            if (entry.first == radius)
                return entry.second;
        auto tiles = armed;
        for (const auto position : armed.positions())
            tiles.draw_chebyshev(position, static_cast<float>(radius));
        armed_cache.emplace_back(radius, std::move(tiles));
        return armed_cache.back().second;
    }
};

bitboard blocked_tiles(const Knowledge& knowledge) {
    auto blocked = knowledge.terrain | cambc::vision::champion_tiles()
        | cambc::vision::camp_tiles() | cambc::vision::teleport_tiles();
    blocked.set(cambc::self().position(), false);
    return blocked;
}

bool try_move(champion& me, vec2 position) {
    try {
        return me.move_absolute(position);
    } catch (const cambc::error&) {
        return false;
    }
}

bool step_towards(Knowledge& knowledge, bitboard goals, const bitboard* avoid = nullptr) {
    auto& me = cambc::self();
    const auto origin = me.position();
    if (!me.can_move() || goals.is_set(origin))
        return false;
    static vec2 stuck_position{-1, -1};
    static int stuck_turns = 0;
    if (stuck_position != origin) {
        stuck_position = origin;
        stuck_turns = 0;
    }
    auto blocked = blocked_tiles(knowledge);
    auto planning = stuck_turns >= 2
        ? blocked : blocked & ~cambc::vision::champion_tiles(team::ally);
    if (avoid) {
        blocked |= *avoid;
        planning |= *avoid;
    }
    goals &= ~planning;
    const auto reachable = blocked.reachable_tiles(
        origin, static_cast<std::uint16_t>(me.base_stats().base_move_speed));
    bool moved = false;
    if (!goals.is_empty()) {
        cambc::distance_field field;
        bitboard visited;
        field.compute_to(planning & ~goals, goals, tiles_around(origin, 0), visited);
        const auto here = field.get(origin);
        if (here < cambc::distance_field::unreachable) {
            auto steps = reachable.positions();
            std::sort(steps.begin(), steps.end(), [&](vec2 a, vec2 b) {
                return field.get(a) < field.get(b);
            });
            for (const auto step : steps) {
                if (field.get(step) >= here)
                    break;
                if (try_move(me, step)) {
                    moved = true;
                    break;
                }
            }
        }
    }
    if (!moved && stuck_turns >= 4) {
        auto options = reachable.positions();
        std::erase(options, origin);
        if (!options.empty()) {
            const auto index = (cambc::round_number() + champion_id(me)) % options.size();
            moved = try_move(me, options[index]);
        }
    }
    stuck_turns = moved ? 0 : stuck_turns + 1;
    return moved;
}

bool step_away(Knowledge& knowledge, const std::vector<vec2>& threats, int) {
    auto& me = cambc::self();
    if (!me.can_move() || threats.empty())
        return false;
    const auto origin = me.position();
    const auto blocked = blocked_tiles(knowledge);
    const auto reachable = blocked.reachable_tiles(
        origin, static_cast<std::uint16_t>(me.base_stats().base_move_speed));
    const auto safety = [&](vec2 tile) {
        int result = std::numeric_limits<int>::max();
        for (const auto threat : threats)
            result = std::min(result, distance(tile, threat));
        return result;
    };
    auto best = origin;
    auto best_safety = safety(origin);
    for (const auto tile : reachable.positions()) {
        const auto value = safety(tile);
        if (value > best_safety) {
            best = tile;
            best_safety = value;
        }
    }
    if (best == origin || best_safety <= safety(origin))
        return step_towards(knowledge, knowledge.ally_spawn);
    return try_move(me, best);
}

bool dash_towards(Knowledge& knowledge, const cambc::ability& ability, const bitboard& goals) {
    auto& me = cambc::self();
    const auto origin = me.position();
    if (goals.is_set(origin))
        return false;
    const auto blocked = blocked_tiles(knowledge);
    cambc::distance_field field;
    bitboard visited;
    field.compute_to(blocked & ~goals, goals, tiles_around(origin, 0), visited);
    const auto here = field.get(origin);
    if (here >= cambc::distance_field::unreachable || here <= 2)
        return false;
    auto landing = tiles_around(origin, 2) & ~blocked;
    const auto& info = ability.info();
    if (info) {
        const auto* dash = std::get_if<cambc::ability_dash>(&*info);
        if (dash && (dash->modifier > 0 || dash->duration > 0))
            landing &= ~knowledge.armed_within(static_cast<int>(dash->radius));
    }
    auto positions = landing.positions();
    if (positions.empty())
        return false;
    const auto best = *std::min_element(positions.begin(), positions.end(), [&](vec2 a, vec2 b) {
        return field.get(a) < field.get(b);
    });
    if (field.get(best) > here - 2)
        return false;
    try {
        return ability.use(best);
    } catch (const cambc::error&) {
        return false;
    }
}

bool splash_reaches(const champion& me, const camp& target, const bitboard* avoid) {
    if (!avoid || me.champion_name() != cambc::champion_type::varg)
        return false;
    bitboard area;
    area.draw_chebyshev(target.position(), cambc::constants::passive_abilities::varg_splash_radius);
    return !(area & *avoid).is_empty();
}

bool basic_attack(cambc::unit& target) {
    auto& me = cambc::self();
    if (!me.can_attack() || !alive(target) || !me.attack_tiles().is_set(target.position()))
        return false;
    me.attack(target);
    for (const auto& ability : me.abilities()) {
        if (ability.is_attack_reset() && alive(target) && ability.is_ready()) {
            try {
                ability.use();
                if (me.can_attack() && alive(target))
                    me.attack(target);
            } catch (const cambc::error&) {
            }
            break;
        }
    }
    return true;
}

struct AbilityMetrics {
    float range = 0;
    float modifier = 0;
    float radius = 0;
    int cooldown = 1;
};

AbilityMetrics ability_metrics(const cambc::ability& ability) {
    AbilityMetrics metrics;
    if (!ability.info())
        return metrics;
    std::visit([&](const auto& info) {
        metrics.cooldown = std::max(1, info.max_cooldown);
        if constexpr (requires { info.range; })
            metrics.range = info.range;
        if constexpr (requires { info.modifier; })
            metrics.modifier = info.modifier;
        if constexpr (requires { info.radius; })
            metrics.radius = info.radius;
    }, *ability.info());
    return metrics;
}

template<class Targets>
bool cast_damage(const Targets& targets, bool allow_exclusive = true, const bitboard* avoid = nullptr) {
    auto& me = cambc::self();
    std::optional<std::tuple<float, float, std::size_t, std::size_t>> best;
    const auto abilities = me.abilities();
    for (std::size_t i = 0; i < abilities.size(); ++i) {
        const auto& ability = abilities[i];
        if (!(ability.is_damage() || ability.is_aoe_damage() || ability.is_cc())
            || !ability.info() || !ability.is_ready())
            continue;
        const auto metrics = ability_metrics(ability);
        if (ability.info().has_value() && std::visit([](const auto& info) {
                return info.exclusive_with_movement;
            }, *ability.info()) && !allow_exclusive)
            continue;
        if (metrics.modifier <= 0 && !ability.is_cc())
            continue;
        for (std::size_t target_index = 0; target_index < targets.size(); ++target_index) {
            const auto& target = targets[target_index];
            if (!alive(target) || distance(me.position(), target.position()) > metrics.range)
                continue;
            if (ability.is_aoe_damage() && avoid) {
                bitboard area;
                area.draw_chebyshev(target.position(), metrics.radius);
                if (!(area & *avoid).is_empty())
                    continue;
            }
            // Strictly better only, so ties keep the first ability and target, as in v2.
            const auto key = std::pair{metrics.modifier, -target.health()};
            if (!best || key > std::pair{std::get<0>(*best), std::get<1>(*best)})
                best = std::tuple{key.first, key.second, i, target_index};
        }
    }
    if (!best)
        return false;
    const auto& ability = abilities[std::get<2>(*best)];
    const auto& target = targets[std::get<3>(*best)];
    try {
        if (ability.is_aoe_damage())
            return ability.use(target.position());
        return ability.use(target);
    } catch (const cambc::error&) {
    }
    return false;
}

void support_spells(bool under_fire) {
    auto& me = cambc::self();
    const auto allies = cambc::vision::champions(team::ally);
    for (const auto& ability : me.abilities()) {
        if (!ability.is_ready())
            continue;
        try {
            if (ability.is_shield() && under_fire) {
                ability.use();
                return;
            }
            if (!ability.is_heal())
                continue;
            const auto metrics = ability_metrics(ability);
            std::optional<champion> target;
            float lowest = std::numeric_limits<float>::max();
            for (const auto& ally : allies) {
                if (ally == me || distance(me.position(), ally.position()) > metrics.range)
                    continue;
                if (ally.max_health() - ally.health() < ability.heal_amount())
                    continue;
                const auto ratio = ally.health() / ally.max_health();
                if (ratio < lowest) {
                    lowest = ratio;
                    target = ally;
                }
            }
            if (target) {
                ability.use(*target);
                return;
            }
        } catch (const cambc::error&) {
        }
    }
}

float burst_estimate(champion& me) {
    float damage = me.strength();
    float best_spell = 0;
    for (const auto& ability : me.abilities()) {
        if (ability.is_attack_reset() && ability.is_ready())
            damage += me.strength();
        else if (ability.is_ready() && (ability.is_damage() || ability.is_aoe_damage() || ability.is_cc())) {
            try {
                best_spell = std::max(best_spell, ability.damage_amount());
            } catch (const cambc::error&) {
            }
        }
    }
    return damage + best_spell;
}

float fighting_power(const std::vector<champion>& champions) {
    float health = 0;
    float damage = 0;
    for (const auto& unit : champions) {
        health += std::max(0.0f, unit.health());
        damage += unit.strength() + 0.25f * unit.focus();
    }
    return health * damage;
}

std::pair<std::optional<float>, std::vector<champion>>
local_advantage(const std::vector<champion>& enemies, int radius = 6) {
    auto& me = cambc::self();
    std::vector<champion> near;
    for (const auto& enemy : enemies)
        if (alive(enemy) && distance(me.position(), enemy.position()) <= radius)
            near.push_back(enemy);
    if (near.empty())
        return {std::nullopt, {}};
    std::vector<champion> allies{me};
    for (const auto& ally : cambc::vision::champions(team::ally))
        if (!(ally == me) && alive(ally) && distance(me.position(), ally.position()) <= radius)
            allies.push_back(ally);
    return {fighting_power(allies) / std::max(1.0f, fighting_power(near)), std::move(near)};
}

struct BuildStep {
    cambc::item_type shard;
    std::uint32_t wanted;
};

const std::vector<BuildStep>& build_for(cambc::champion_type type) {
    using I = cambc::item_type;
    static const std::vector<BuildStep> melee{
        {I::jungle_shard_of_health, 5}, {I::durability_shard_of_strength, 5},
        {I::bruiser_shard_of_health, 5}, {I::monster_shard_of_strength, 5},
        {I::bruiser_shard_of_health, 10}, {I::bruiser_shard_of_strength, 60}};
    static const std::vector<BuildStep> ren{
        {I::jungle_shard_of_health, 5}, {I::bruiser_shard_of_health, 5},
        {I::durability_shard_of_strength, 5}, {I::bruiser_shard_of_health, 10},
        {I::bruiser_shard_of_strength, 60}};
    static const std::vector<BuildStep> rythm{
        {I::jungle_shard_of_health, 5}, {I::durability_shard_of_strength, 5},
        {I::bruiser_shard_of_health, 60}};
    static const std::vector<BuildStep> varg{
        {I::jungle_shard_of_strength, 5}, {I::durability_shard_of_health, 5},
        {I::bruiser_shard_of_strength, 10}, {I::bruiser_shard_of_health, 5},
        {I::bruiser_shard_of_strength, 60}};
    static const std::vector<BuildStep> caster{
        {I::bruiser_shard_of_focus, 10}, {I::bruiser_shard_of_health, 5},
        {I::bruiser_shard_of_focus, 15}, {I::durability_shard_of_focus, 5},
        {I::bruiser_shard_of_focus, 60}};
    static const std::vector<BuildStep> strength{
        {I::monster_shard_of_strength, 5}, {I::jungle_shard_of_health, 5},
        {I::power_shard_of_strength, 60}};
    static const std::vector<BuildStep> gold{
        {I::treasure_shard_of_strength, 5}, {I::monster_shard_of_strength, 5},
        {I::power_shard_of_strength, 60}};
    static const std::vector<BuildStep> ordinary_caster{
        {I::monster_shard_of_focus, 5}, {I::jungle_shard_of_health, 5},
        {I::power_shard_of_focus, 60}};
    switch (type) {
    case cambc::champion_type::vendetta:
    case cambc::champion_type::issac:
    case cambc::champion_type::marcella: return melee;
    case cambc::champion_type::ren: return ren;
    case cambc::champion_type::ryth: return rythm;
    case cambc::champion_type::varg: return varg;
    case cambc::champion_type::vesper_vale: return gold;
    case cambc::champion_type::willow: return ordinary_caster;
    case cambc::champion_type::stellar:
    case cambc::champion_type::prism:
    case cambc::champion_type::cassi:
    case cambc::champion_type::tavi: return caster;
    default: return strength;
    }
}

std::uint32_t owned_shards(const cambc::enum_map<cambc::item_type>& items, cambc::item_type shard) {
    const auto emblem = cambc::item_type{static_cast<std::uint32_t>(shard) + 1};
    return items[shard] + shard.combine_count() * items[emblem];
}

void shop() {
    auto& me = cambc::self();
    try {
        const auto lock = cambc::consumable_type::altar_lock;
        if (me.gold_count() >= lock.cost() && me.can_buy(lock))
            me.buy(lock);
    } catch (const cambc::error&) {
    }
    for (const auto step : build_for(me.champion_name())) {
        const auto owned = owned_shards(me.item_count(), step.shard);
        if (owned >= step.wanted)
            continue;
        const auto missing = step.wanted - owned;
        const auto count = std::min(missing, me.gold_count() / step.shard.cost());
        if (count == 0)
            return;
        try {
            if (me.can_buy(step.shard, count))
                me.buy(step.shard, count);
        } catch (const cambc::error&) {
            return;
        }
        if (count < missing)
            return;
    }
}

class BotImpl {
public:
    explicit BotImpl(Bot& bot) : bot_(bot) {}
    void play_turn();
    bool place_ward();

private:
    Bot& bot_;
    Knowledge& k() { return *bot_.knowledge_; }
    bool place_altar_lock(const std::vector<champion>& enemies);
    std::vector<int> usable_altars();
    bool should_bank(const std::vector<champion>& enemies);
    void bank();
    bool fight_enemies(const std::vector<champion>& enemies, bool aggressive = false);
    std::vector<camp> target_camps();
    int choose_target();
    void farm();
    void travel(const bitboard& goals);
    void capture(GroupInfo& info);
    void engage(std::vector<camp>& camps);
};

bool BotImpl::place_ward() {
    auto& me = cambc::self();
    // The scan runs last: it stops at ward_reserve rather than run the turn dry.
    const auto phase = cambc::round_number() + champion_id(me);
    if (me.ward_cooldown() > 0 || cambc::fuel_remaining() < ward_fuel)
        return false;
    bitboard mine;
    bitboard tiles;
    try {
        mine = me.visible_tiles();
        tiles = me.ward_placement_tiles() & ~k().walls;
    } catch (const cambc::error&) {
        return false;
    }
    const auto hidden = ~mine;
    const auto bush = k().bushes & hidden;
    const auto ahead = k().enemy_half & hidden;
    const auto gain = [&](vec2 tile) {
        try {
            const auto seen = cambc::ward::visible_tiles_from(tile);
            return static_cast<int>((seen & hidden).count()
                + 2 * (seen & bush).count() + (seen & ahead).count());
        } catch (const cambc::error&) {
            return 0;
        }
    };
    int current = 0;
    for (const auto ward : me.ward_positions())
        current = std::max(current, gain(ward));
    const auto position = me.position();
    vec2 best{-1, -1};
    int best_gain = static_cast<int>(current * 1.2f + 6);
    // Rotate the start so a cut-short scan does not always skip the same corner.
    auto candidates = tiles.positions();
    if (!candidates.empty())
        std::rotate(candidates.begin(), candidates.begin() + phase % candidates.size(), candidates.end());
    for (const auto tile : candidates) {
        if (cambc::fuel_remaining() < ward_reserve)
            break;
        if (distance(position, tile) < 2)
            continue;
        const auto value = gain(tile);
        if (value > best_gain) {
            best = tile;
            best_gain = value;
        }
    }
    if (best.x < 0)
        return false;
    try {
        return me.place_ward(best);
    } catch (const cambc::error&) {
        return false;
    }
}

bool BotImpl::place_altar_lock(const std::vector<champion>& enemies) {
    auto& me = cambc::self();
    const auto& lock = me.consumables()[cambc::consumable_type::altar_lock];
    if (lock.count() == 0)
        return false;
    for (const auto& enemy : enemies) {
        if (!enemy.is_submitting_gems())
            continue;
        for (const auto altar : k().all_altars) {
            if (distance(altar, enemy.position()) > cambc::constants::submit_gems_range
                || distance(me.position(), altar) > 2 || cambc::vision::has_altar_lock(altar))
                continue;
            try {
                if (lock.use(altar))
                    return true;
            } catch (const cambc::error&) {
            }
        }
    }
    return false;
}

std::vector<int> BotImpl::usable_altars() {
    auto open = k().open_altars();
    const auto visible = cambc::vision::visible_tiles();
    std::vector<int> result;
    for (const auto index : open) {
        const auto altar = k().altars[static_cast<std::size_t>(index)];
        if (visible.is_set(altar)) {
            try {
                k().locked[static_cast<std::size_t>(index)] =
                    cambc::vision::has_altar_lock(altar)
                    && cambc::vision::altar_lock_at(altar).is_enemy();
            } catch (const cambc::error&) {
                k().locked[static_cast<std::size_t>(index)] = false;
            }
        }
        if (!k().locked[static_cast<std::size_t>(index)])
            result.push_back(index);
    }
    return result.empty() ? open : result;
}

bool BotImpl::should_bank(const std::vector<champion>& enemies) {
    auto& me = cambc::self();
    const auto gems = me.gem_count();
    if (gems == 0)
        return false;
    if (k().open_altars().empty())
        return false;
    const auto position = me.position();
    const auto altar_distance = k().nearest_altar_distance(position);
    const auto rounds_left = cambc::constants::max_rounds - cambc::round_number();
    if (rounds_left < altar_distance * 1.4f + std::ceil(gems / 10.0f) + 15)
        return true;
    if (cambc::round_number() < bot_.bank_after_)
        return false;
    if (cambc::global_submitted_gems(team::ally) + gems >= cambc::constants::winning_gems)
        return true;
    if (gems >= bank_gems)
        return true;
    if (altar_distance <= near_altar && target_camps().empty())
        return true;
    if (bot_.target_ >= 0) {
        const auto wait = static_cast<int>(k().available[bot_.target_])
            - static_cast<int>(cambc::round_number());
        if (wait > 0 && wait >= altar_distance)
            return true;
    }
    if (gems >= 10 && !enemies.empty())
        return true;
    return me.health() < me.max_health() * 0.5f;
}

void BotImpl::bank() {
    auto& me = cambc::self();
    const auto position = me.position();
    const auto altars = usable_altars();
    const auto reach = cambc::constants::submit_gems_range;
    for (const int index : altars) {
        const auto altar = k().altars[static_cast<std::size_t>(index)];
        if (distance(position, altar) <= reach) {
            try {
                me.submit_gems(altar);
                return;
            } catch (const cambc::error&) {
            }
        }
    }
    bitboard goals;
    for (const int index : altars)
        goals |= k().altar_spots[static_cast<std::size_t>(index)];
    if (goals.is_empty())
        for (const int index : altars)
            goals |= tiles_around(k().altars[static_cast<std::size_t>(index)], reach);
    step_towards(k(), goals);
}

bool BotImpl::fight_enemies(const std::vector<champion>& enemies, bool aggressive) {
    auto& me = cambc::self();
    if (enemies.empty())
        return false;
    std::vector<champion> worth;
    const auto burst = burst_estimate(me);
    for (const auto& enemy : enemies) {
        if (!alive(enemy) || distance(me.position(), enemy.position()) > std::max(me.attack_range(), 4))
            continue;
        std::uint32_t gems = 0;
        try {
            gems = enemy.gem_count();
        } catch (const cambc::error&) {
        }
        if (aggressive || enemy.health() <= burst
            || (gems >= 20 && me.health() >= enemy.health() * 1.2f))
            worth.push_back(enemy);
    }
    if (worth.empty())
        return false;
    auto target = *std::min_element(worth.begin(), worth.end(), [](const champion& a, const champion& b) {
        return a.health() < b.health();
    });
    bool acted = cast_damage(std::vector<champion>{target});
    acted = basic_attack(target) || acted;
    if (!acted && me.can_move()) {
        const auto goals = tiles_around(target.position(), me.attack_range());
        acted = step_towards(k(), goals);
        basic_attack(target);
    }
    return acted;
}

std::vector<camp> BotImpl::target_camps() {
    std::vector<camp> result;
    if (bot_.target_ < 0)
        return result;
    for (const auto& entry : k().seen)
        if (std::get<1>(entry) == bot_.target_ && std::get<2>(entry) > 0)
            result.push_back(std::get<0>(entry));
    return result;
}

int BotImpl::choose_target() {
    auto& me = cambc::self();
    const auto now = cambc::round_number();
    const auto position = me.position();
    const float dps = [&] {
        float result = me.strength();
        for (const auto& ability : me.abilities()) {
            if (!ability.info())
                continue;
            const auto metrics = ability_metrics(ability);
            if (ability.is_attack_reset())
                result += me.strength() / metrics.cooldown;
            else if (ability.is_damage() || ability.is_aoe_damage() || ability.is_cc())
                result += me.focus() * metrics.modifier / metrics.cooldown;
        }
        if (me.champion_name() == cambc::champion_type::varg)
            result *= 1.5f;
        result *= me.base_stats().camp_damage_multiplier;
        return std::max(result, 1.0f);
    }();
    const float budget = me.max_health() * (1.0f - low_health);
    std::array<int, claim_slots> claims{};
    read_claims(claims);
    std::vector<int> others_on(k().groups.size(), 0);
    for (int i = 0; i < claim_slots; ++i)
        if (claims[static_cast<std::size_t>(i)] >= 0 && i != bot_.slot_
            && claims[static_cast<std::size_t>(i)] < static_cast<int>(others_on.size()))
            ++others_on[static_cast<std::size_t>(claims[static_cast<std::size_t>(i)])];
    const bool late = now >= 700 && !k().open_altars().empty();
    float best_score = -1.0f;
    int best_index = -1;
    std::vector<std::tuple<float, int, float>> scored;
    scored.reserve(k().scoring.size());
    for (const auto& entry : k().scoring) {
        const int index = entry.index;
        if (late && entry.late_value <= 0)
            continue;
        const float team_size = 1 + others_on[static_cast<std::size_t>(index)];
        const float kill = k().remaining[static_cast<std::size_t>(index)] / (dps * team_size);
        const float travel = std::max(std::abs(entry.cx - position.x), std::abs(entry.cy - position.y)) * 1.25f;
        const float wait = static_cast<float>(std::max(k().available[static_cast<std::size_t>(index)],
            k().avoid[static_cast<std::size_t>(index)])) - now - travel;
        float busy = travel + kill + 0.4f * entry.strength * kill / team_size / budget * entry.trip_cost + entry.fixed;
        if (wait > 0)
            busy += wait;
        float score = (late ? entry.late_value : entry.early_value)
            / (busy * team_size + k().capture_time);
        if (index == bot_.target_)
            score *= 1.15f;
        scored.emplace_back(score, index, travel);
        if (score > best_score) {
            best_score = score;
            best_index = index;
        }
    }
    if (best_index < 0 || cambc::fuel_remaining() < refine_fuel)
        return best_index;
    std::sort(scored.begin(), scored.end(), std::greater<>{});
    bitboard origin;
    origin.set(position);
    bitboard visited;
    cambc::distance_field field;
    field.compute(k().terrain, origin, visited);
    std::optional<std::pair<float, int>> best;
    for (std::size_t i = 0; i < std::min<std::size_t>(candidates, scored.size()); ++i) {
        const auto [score, index, estimate] = scored[i];
        const auto walk = field.get(k().groups[static_cast<std::size_t>(index)].anchor);
        if (walk >= cambc::distance_field::unreachable)
            continue;
        const auto refined = score * (estimate + 10.0f) / (walk + 10.0f);
        if (!best || refined > best->first)
            best = std::pair{refined, index};
    }
    return best ? best->second : best_index;
}

void BotImpl::farm() {
    const auto now = cambc::round_number();
    if (bot_.target_ < 0
        || k().available[static_cast<std::size_t>(bot_.target_)] > now + 25
        || (now % 10 == champion_id(cambc::self()) % 10 && cambc::fuel_remaining() > replan_fuel))
        bot_.target_ = choose_target();
    write_claim(bot_.slot_, bot_.target_);
    if (bot_.target_ < 0) {
        step_towards(k(), k().ally_spawn);
        return;
    }
    auto* info = &k().groups[static_cast<std::size_t>(bot_.target_)];
    auto camps = target_camps();
    if (!camps.empty()) {
        engage(camps);
        return;
    }
    const auto visible = cambc::vision::visible_tiles();
    bool in_view = !(info->tiles & visible).is_empty();
    if (in_view) {
        if (k().reward_ready[static_cast<std::size_t>(bot_.target_)]) {
            capture(*info);
            return;
        }
        if (k().available[static_cast<std::size_t>(bot_.target_)] > now) {
            bot_.target_ = choose_target();
            write_claim(bot_.slot_, bot_.target_);
            if (bot_.target_ < 0)
                return;
            info = &k().groups[static_cast<std::size_t>(bot_.target_)];
            in_view = !(info->tiles & visible).is_empty();
        }
    }
    const auto position = cambc::self().position();
    if (k().available[static_cast<std::size_t>(bot_.target_)] > now
        || (in_view && !k().reward_ready[static_cast<std::size_t>(bot_.target_)])) {
        bitboard ring;
        for (const auto tile : info->positions)
            ring.draw_chebyshev(tile, 1.0f);
        const auto goals = ring & ~k().spawn_tiles;
        if (k().spawn_tiles.is_set(position) || !goals.is_set(position))
            travel(goals);
        return;
    }
    bitboard goals = info->tiles;
    for (const auto tile : info->positions)
        goals.draw_chebyshev(tile, 1.0f);
    travel(goals);
}

void BotImpl::travel(const bitboard& goals) {
    auto& me = cambc::self();
    for (const auto& ability : me.abilities())
        if (ability.is_dash() && ability.is_ready() && dash_towards(k(), ability, goals))
            break;
    step_towards(k(), goals);
}

void BotImpl::capture(GroupInfo& info) {
    auto& me = cambc::self();
    std::vector<champion> intruders;
    for (const auto& enemy : cambc::vision::champions(team::enemy))
        if (alive(enemy) && info.tiles.is_set(enemy.position()))
            intruders.push_back(enemy);
    if (!intruders.empty()) {
        ++bot_.contested_;
        const auto ratio = local_advantage(intruders, 8).first;
        if (ratio && *ratio >= 1.0f && fight_enemies(intruders, true))
            return;
        if (bot_.contested_ > contest_turns) {
            k().avoid[static_cast<std::size_t>(info.index)] = cambc::round_number() + contest_backoff;
            bot_.target_ = -1;
            bot_.contested_ = 0;
            return;
        }
    } else {
        bot_.contested_ = 0;
    }
    std::vector<champion> allies;
    for (const auto& ally : cambc::vision::champions(team::ally))
        if (!(ally == me) && info.tiles.is_set(ally.position()))
            allies.push_back(ally);
    if (info.tiles.is_set(me.position())) {
        for (const auto& ally : allies)
            if (champion_id(ally) < champion_id(me)) {
                k().captured(info.index);
                bot_.target_ = -1;
                return;
            }
        return;
    }
    if (!allies.empty()) {
        k().captured(info.index);
        bot_.target_ = -1;
        return;
    }
    step_towards(k(), info.tiles);
}

void BotImpl::engage(std::vector<camp>& camps) {
    auto& me = cambc::self();
    const auto position = me.position();
    bool under_fire = false;
    float incoming = 0;
    for (const auto& enemy_camp : camps) {
        if (enemy_camp.strength() > 0
            && distance(position, enemy_camp.position()) <= enemy_camp.attack_range())
            under_fire = true;
        if (alive(enemy_camp) && enemy_camp.strength() > 0
            && enemy_camp.health() < enemy_camp.max_health())
            incoming += enemy_camp.strength();
    }
    support_spells(under_fire);
    if (incoming > 0 && me.health() < incoming * 2) {
        std::vector<vec2> threats;
        for (const auto& enemy_camp : camps)
            threats.push_back(enemy_camp.position());
        step_away(k(), threats, 4);
        return;
    }
    const auto& avoid = bot_.target_ >= 0 ? &k().collateral(bot_.target_) : nullptr;
    auto target = std::min_element(camps.begin(), camps.end(), [&](const camp& a, const camp& b) {
        const auto splash_a = splash_reaches(me, a, avoid);
        const auto splash_b = splash_reaches(me, b, avoid);
        return splash_a != splash_b ? !splash_a : a.health() < b.health();
    });
    if (target == camps.end())
        return;
    if (splash_reaches(me, *target, avoid)) {
        if (bot_.target_ >= 0)
            k().avoid[static_cast<std::size_t>(bot_.target_)] = cambc::round_number() + contest_backoff;
        bot_.target_ = -1;
        return;
    }
    if (basic_attack(*target)) {
        cast_damage(camps, true, avoid);
        return;
    }
    const bool cast = cast_damage(camps, true, avoid);
    if (me.can_move())
        step_towards(k(), tiles_around(target->position(), me.attack_range()));
    basic_attack(*target);
    if (!cast)
        cast_damage(camps, true, avoid);
}

void BotImpl::play_turn() {
    auto& me = cambc::self();
    auto& knowledge = k();
    knowledge.observe();
    if (!me.is_alive()) {
        bot_.healing_ = false;
        bot_.target_ = -1;
        bot_.last_health_ = -1;
        write_claim(bot_.slot_, -1);
        shop();
        return;
    }
    const float health = me.health();
    const float damage = bot_.last_health_ < 0 ? 0 : std::max(0.0f, bot_.last_health_ - health);
    bot_.last_health_ = health;
    if (me.is_submitting_gems()) {
        if (damage > 0 && health <= damage * (me.remaining_channel_time() + 1)) {
            me.cancel_submit_gems();
            bot_.bank_after_ = cambc::round_number() + ambush_backoff;
        } else {
            return;
        }
    } else if (me.is_recalling() || me.is_teleporting()) {
        return;
    }

    const auto position = me.position();
    const bool at_spawn = knowledge.ally_spawn.is_set(position);
    if (at_spawn || me.champion_name() == cambc::champion_type::tavi)
        shop();
    if (at_spawn && bot_.healing_ && me.health() < me.max_health() * healed_health)
        return;
    bot_.healing_ = false;

    std::vector<champion> enemies;
    for (const auto& enemy : cambc::vision::champions(team::enemy))
        if (alive(enemy))
            enemies.push_back(enemy);
    std::vector<camp> hostile_camps;
    for (const auto& entry : knowledge.seen) {
        const auto& c = std::get<0>(entry);
        if (std::get<2>(entry) > 0 && c.strength() > 0 && std::get<2>(entry) < c.max_health())
            hostile_camps.push_back(c);
    }
    place_altar_lock(enemies);

    if (damage > 0 && me.gem_count() > 0 && !at_spawn && enemies.empty()) {
        bool in_camp_range = false;
        for (const auto& c : hostile_camps)
            if (distance(position, c.position()) <= c.attack_range())
                in_camp_range = true;
        if (!in_camp_range) {
            bot_.bank_after_ = std::max(bot_.bank_after_, cambc::round_number() + ambush_backoff);
            step_towards(knowledge, knowledge.ally_spawn);
            return;
        }
    }

    const bool linked = me.champion_name() == cambc::champion_type::cassi
        || me.champion_name() == cambc::champion_type::issac;
    const float retreat_health = linked ? linked_low_health : low_health;
    if (!at_spawn && health < me.max_health() * retreat_health) {
        std::vector<vec2> threats;
        for (const auto& enemy : enemies)
            if (distance(position, enemy.position()) <= 6)
                threats.push_back(enemy.position());
        for (const auto& c : hostile_camps)
            if (distance(position, c.position()) <= 4)
                threats.push_back(c.position());
        if (me.gem_count() > 0 && knowledge.nearest_altar_distance(position) <= 2
            && enemies.empty() && !knowledge.open_altars().empty()) {
            bank();
            return;
        }
        if (threats.empty()) {
            try {
                me.recall();
                bot_.healing_ = true;
            } catch (const cambc::error&) {
            }
            return;
        }
        std::vector<champion> pressing;
        for (const auto& enemy : enemies)
            if (distance(position, enemy.position()) <= enemy.attack_range() + 1)
                pressing.push_back(enemy);
        if (!pressing.empty() && fight_enemies(pressing, true))
            return;
        step_away(knowledge, threats, 4);
        return;
    }

    auto [ratio, near] = local_advantage(enemies);
    if (ratio) {
        if (*ratio >= fight_edge && fight_enemies(near, true))
            return;
        if (*ratio < retreat_edge && (me.gem_count() > 0 || me.health() < me.max_health() * 0.6f)) {
            std::vector<vec2> threats;
            for (const auto& enemy : near)
                threats.push_back(enemy.position());
            step_away(knowledge, threats, 6);
            return;
        }
    }
    if (ratio) {
        std::vector<champion> pressing;
        for (const auto& enemy : near)
            if (distance(position, enemy.position()) <= std::max(enemy.attack_range(), 4) + 1)
                pressing.push_back(enemy);
        if (!pressing.empty()) {
            if (*ratio >= press_edge && fight_enemies(pressing, true))
                return;
            if (*ratio < press_edge) {
                std::vector<vec2> threats;
                for (const auto& enemy : near)
                    threats.push_back(enemy.position());
                step_away(knowledge, threats, 6);
                return;
            }
        }
    }
    if (fight_enemies(enemies))
        return;
    if (should_bank(enemies)) {
        bank();
        return;
    }
    if (!at_spawn && me.gem_count() == 0 && me.gold_count() >= shop_gold
        && hostile_camps.empty() && enemies.empty() && me.champion_name() != cambc::champion_type::tavi
        && target_camps().empty()) {
        me.recall();
        bot_.healing_ = true;
        return;
    }
    farm();
}
Bot::Bot() = default;

Bot::~Bot() = default;
Bot::Bot(Bot&&) noexcept = default;
Bot& Bot::operator=(Bot&&) noexcept = default;

void Bot::play_turn() {
    if (!knowledge_) {
        knowledge_ = std::make_unique<Knowledge>();
        const auto plan = draft_plan();
        const auto pick = draft_pick(cambc::self().champion_name());
        for (std::size_t i = 0; i < plan.size(); ++i)
            if (plan[i] == pick) {
                slot_ = static_cast<int>(i);
                break;
            }
        if (slot_ < 0)
            slot_ = static_cast<int>(champion_id(cambc::self()) % claim_slots);
    }
    BotImpl bot{*this};
    bot.play_turn();
    if (cambc::self().is_alive() && !knowledge_->ally_spawn.is_set(cambc::self().position()))
        bot.place_ward();
}
