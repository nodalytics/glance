#pragma once

#include <mutex>
#include <random>
#include <string>
#include <unordered_map>

#include <httplib.h>

#include "control_service.h"
#include "scraper.h"

namespace glance {

// The Slumbot-mirroring control plane, exposed under glance's plain, flat
// paths: POST /login, POST /new_hand, POST /act. It mirrors the Slumbot
// protocol's bodies, token rules and action grammar (research/slumbot.md), but
// it is NOT a poker game engine: it does not deal cards or run a game. It is a
// thin real-window CONTROL + TRANSLATION surface over the existing
// TableScraper (state readback) and ControlService (click injection).
//
// What is REAL here:
//   - the opaque session token + in-memory session map (/login);
//   - the action-string validator (slumbot_action.h, a 1:1 port of the
//     reference ParseAction) run on every /act;
//   - the action -> named-control-action -> click mapping (f/c/k/b<n> ->
//     "fold"/"call"/"check"/"raise", resolved through the mapping's "actions"
//     and injected via ControlService);
//   - the Slumbot-shaped state readback (hole_cards/board/client_pos) built
//     from the last parsed TableState.
//
// What is ROADMAP (and says so in code + docs): there is no auth (any creds
// mint a token — this is a local tool), glance does not deal cards or decide
// whose turn it is, it does not auto-recapture after a click (the client calls
// /grab or /capture again to see the result), and entering a specific bet size
// for b<n> is not yet typed (only the "raise" button is clicked).
//
// Errors ride inside a 200 body as `error_msg` (the Slumbot convention), so
// clients parse the body, not just the status code. A genuinely malformed HTTP
// request (unparseable JSON) is still a 400.
class SlumbotRoutes {
 public:
  SlumbotRoutes(TableScraper* scraper, ControlService* control);
  // Register /login, /new_hand, /act on srv. Call once per server.
  void install(httplib::Server& srv);

 private:
  struct Session {
    std::string action;  // accumulated Slumbot action history for this hand
  };

  // Mint a new opaque session token and store an empty session for it.
  std::string mint_session();
  // Build the Slumbot-shaped response from the current parsed table state.
  nlohmann::json shaped(const std::string& old_action, const std::string& action,
                        const std::string& token) const;

  TableScraper* scraper_;
  ControlService* ctrl_;

  mutable std::mutex mu_;
  std::unordered_map<std::string, Session> sessions_;
  std::mt19937_64 rng_{std::random_device{}()};
};

}  // namespace glance
