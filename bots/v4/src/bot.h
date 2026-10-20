#pragma once

#include <cstdint>
#include <memory>

class Knowledge;
class BotImpl;

class Bot {
public:
    Bot();
    ~Bot();
    Bot(Bot&&) noexcept;
    Bot& operator=(Bot&&) noexcept;
    Bot(const Bot&) = delete;
    Bot& operator=(const Bot&) = delete;

    void play_turn();

private:
    friend class BotImpl;
    std::unique_ptr<Knowledge> knowledge_;
    int slot_ = -1;
    int target_ = -1;
    int contested_ = 0;
    std::uint32_t bank_after_ = 0;
    float last_health_ = -1.0f;
    bool healing_ = false;
};
