#include <cambc.h>
#include "draft.h"

#include <algorithm>
#include <array>
#include <cstdint>
#include <vector>

void play_draft() {
    using cambc::champion_draft;
    constexpr std::array priority{
        champion_draft::cassi_and_issac,
        champion_draft::stellar,
        champion_draft::ren,
        champion_draft::varg,
        champion_draft::ryth,
        champion_draft::tavi,
        champion_draft::vendetta,
        champion_draft::marcella,
        champion_draft::vesper_vale,
        champion_draft::prism,
        champion_draft::willow,
    };

    const auto chosen = cambc::draft::current_draft(cambc::team::ally);
    const auto next = std::find_if(priority.begin(), priority.end(), [&](champion_draft pick) {
        return std::find(chosen.begin(), chosen.end(), pick) == chosen.end();
    });
    if (next == priority.end())
        return;

    cambc::draft::pick(*next);
    std::vector<std::uint8_t> memory{1, static_cast<std::uint8_t>(chosen.size() + 1)};
    for (const auto pick : chosen)
        memory.push_back(static_cast<std::uint8_t>(pick));
    memory.push_back(static_cast<std::uint8_t>(*next));
    memory.push_back(0);
    cambc::draft_memory = memory;
}
