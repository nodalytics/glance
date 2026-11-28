#include "server_slumbot.h"

#include <cstdint>
#include <cstdio>
#include <string>

#include <nlohmann/json.hpp>

#include "slumbot_action.h"

namespace glance {

SlumbotRoutes::SlumbotRoutes(TableScraper* scraper, ControlService* control)
    : scraper_(scraper), ctrl_(control) {}

namespace {

// A 400 for a genuinely malformed HTTP request (unparseable JSON / wrong type).
void bad_request(httplib::Response& res, const std::string& msg) {
  nlohmann::json j;
  j["error"] = msg;
  res.status = 400;
  res.set_content(j.dump(), "application/json");
}

// A Slumbot-style protocol error: 200 with an `error_msg` key (plus the token
// when we have one, so the client keeps playing with the same session).
void error_msg(httplib::Response& res, const std::string& msg, const std::string& token = "") {
  nlohmann::json j;
  j["error_msg"] = msg;
  if (!token.empty()) j["token"] = token;
  res.set_content(j.dump(), "application/json");
}

// The control-action name for the FINAL action token of `incr`:
//   f -> "fold"   c -> "call"   k -> "check"   b<n> -> "raise"
// '/' and the digits of a bet are skipped; "" when incr carries no action.
std::string last_action_name(const std::string& incr) {
  std::string name;
  for (std::size_t k = 0; k < incr.size(); ++k) {
    const char ch = incr[k];
    if (ch == 'f') {
      name = "fold";
    } else if (ch == 'c') {
      name = "call";
    } else if (ch == 'k') {
      name = "check";
    } else if (ch == 'b') {
      name = "raise";
      while (k + 1 < incr.size() && incr[k + 1] >= '0' && incr[k + 1] <= '9') ++k;
    }
    // '/' and stray digits are ignored.
  }
  return name;
}

}  // namespace

std::string SlumbotRoutes::mint_session() {
  std::lock_guard<std::mutex> g(mu_);
  // A UUID-shaped hex token from two 64-bit draws. Opaque and unguessable
  // enough for a local tool; this is not an auth secret.
  const std::uint64_t a = rng_();
  const std::uint64_t b = rng_();
  char buf[40];
  std::snprintf(buf, sizeof(buf), "%08x-%04x-%04x-%04x-%012llx",
                static_cast<unsigned>(a >> 32), static_cast<unsigned>((a >> 16) & 0xffff),
                static_cast<unsigned>(a & 0xffff), static_cast<unsigned>(b >> 48),
                static_cast<unsigned long long>(b & 0xffffffffffffULL));
  std::string token(buf);
  sessions_[token] = Session{};
  return token;
}

nlohmann::json SlumbotRoutes::shaped(const std::string& old_action, const std::string& action,
                                     const std::string& token) const {
  nlohmann::json j;
  j["old_action"] = old_action;
  j["action"] = action;
  j["token"] = token;

  int client_pos = 0;  // 0 = big blind, 1 = small blind (Slumbot convention)
  nlohmann::json hole = nlohmann::json::array();
  nlohmann::json board = nlohmann::json::array();
  const TableState* st = scraper_ ? scraper_->last_state() : nullptr;
  if (st) {
    // Hero is seat index 0 in the engine (seats[0] is the bot). In heads-up the
    // button is the small blind, so if the hero holds the button they are the
    // SB (client_pos 1); otherwise the big blind (client_pos 0). Best-effort
    // from the parsed dealer position — a real-window extra over Slumbot's own
    // binary client_pos.
    if (st->dealer_position) client_pos = (*st->dealer_position == 0) ? 1 : 0;
    if (!st->seats.empty()) hole = st->seats[0].cards;
    board = st->board;
    // Glance extra: the full parsed state JSON when a capture is available.
    j["state"] = to_json(*st);
  }
  j["client_pos"] = client_pos;
  j["hole_cards"] = hole;
  j["board"] = board;
  return j;
}

void SlumbotRoutes::install(httplib::Server& srv) {
  // POST /login {username?, password?} -> {token}
  // No real auth: this is a local tool, so any (or empty) credentials mint a
  // session token. The username/password are accepted and ignored.
  srv.Post("/login", [this](const httplib::Request& req, httplib::Response& res) {
    if (!req.body.empty()) {
      nlohmann::json j = nlohmann::json::parse(req.body, nullptr, /*allow_exceptions=*/false);
      if (j.is_discarded()) {
        bad_request(res, "invalid JSON body");
        return;
      }
    }
    nlohmann::json out;
    out["token"] = mint_session();
    res.set_content(out.dump(), "application/json");
  });

  // POST /new_hand {token?} -> Slumbot-shaped response from the current state.
  // The token may be omitted ONLY on the very first call (then one is minted).
  srv.Post("/new_hand", [this](const httplib::Request& req, httplib::Response& res) {
    std::string token;
    if (!req.body.empty()) {
      nlohmann::json j = nlohmann::json::parse(req.body, nullptr, /*allow_exceptions=*/false);
      if (j.is_discarded()) {
        bad_request(res, "invalid JSON body");
        return;
      }
      if (j.contains("token") && j["token"].is_string()) token = j["token"].get<std::string>();
    }

    if (token.empty()) {
      // First-call case: mint a session (token optional only here).
      token = mint_session();
    } else {
      std::lock_guard<std::mutex> g(mu_);
      auto it = sessions_.find(token);
      if (it == sessions_.end()) {
        error_msg(res, "unknown token; call /login or omit the token on the first /new_hand");
        return;
      }
      it->second.action.clear();  // a new hand resets the action history
    }

    if (!scraper_ || !scraper_->last_state()) {
      error_msg(res, "no table state yet; POST a frame to /capture or call /grab first", token);
      return;
    }
    res.set_content(shaped("", "", token).dump(), "application/json");
  });

  // POST /act {token, incr} -> updated Slumbot-shaped response.
  // Validates incr with the ported ParseAction, maps its last action token to a
  // named control action, and injects a click through the ControlService.
  srv.Post("/act", [this](const httplib::Request& req, httplib::Response& res) {
    nlohmann::json j = nlohmann::json::parse(req.body, nullptr, /*allow_exceptions=*/false);
    if (j.is_discarded() || !j.is_object()) {
      bad_request(res, "invalid JSON body");
      return;
    }
    const std::string token = j.value("token", std::string());
    if (token.empty()) {
      error_msg(res, "missing token");
      return;
    }
    if (!j.contains("incr") || !j["incr"].is_string()) {
      error_msg(res, "missing incr (the incremental action string)", token);
      return;
    }
    const std::string incr = j["incr"].get<std::string>();

    std::string old_action;
    {
      std::lock_guard<std::mutex> g(mu_);
      auto it = sessions_.find(token);
      if (it == sessions_.end()) {
        error_msg(res, "unknown token; call /login or /new_hand first");
        return;
      }
      old_action = it->second.action;
    }
    if (incr.empty()) {
      error_msg(res, "empty incr", token);
      return;
    }

    // Build and validate the accumulated action with the ported parser. incr is
    // concatenated onto the history; if that does not parse but inserting a
    // street separator does, the separator was the missing street transition
    // (glance is not the dealer, so it lets the parser decide which is legal).
    std::string candidate = old_action + incr;
    slumbot::ParsedAction parsed = slumbot::parse_action(candidate);
    if (!parsed.ok && !old_action.empty()) {
      const std::string alt = old_action + "/" + incr;
      const slumbot::ParsedAction p2 = slumbot::parse_action(alt);
      if (p2.ok) {
        candidate = alt;
        parsed = p2;
      }
    }
    if (!parsed.ok) {
      error_msg(res, "illegal action '" + incr + "': " + parsed.error, token);
      return;
    }

    // Map the last action token to a named control action from the mapping.
    const std::string name = last_action_name(incr);
    if (name.empty()) {
      error_msg(res, "incr '" + incr + "' carries no action to click", token);
      return;
    }
    std::string target;
    if (!scraper_ || !scraper_->mapping().action_target(name, target)) {
      error_msg(res,
                "the mapping has no \"" + name + "\" action (add it to the mapping's \"actions\")",
                token);
      return;
    }

    // Inject the click. This fails (and is reported, not fatal) when the table
    // is not anchored in the last capture or the backend has no display.
    nlohmann::json detail;
    std::string err;
    ControlService::ClickRequest cr;
    cr.target = name;
    if (!ctrl_ || !ctrl_->click(cr, detail, &err)) {
      error_msg(res, "could not inject '" + name + "': " + err, token);
      return;
    }

    // Commit the accumulated action to the session and reply.
    {
      std::lock_guard<std::mutex> g(mu_);
      auto it = sessions_.find(token);
      if (it != sessions_.end()) it->second.action = candidate;
    }
    nlohmann::json out = shaped(old_action, candidate, token);
    out["injected"] = detail;  // glance extra: what was clicked (audit)
    res.set_content(out.dump(), "application/json");
  });
}

}  // namespace glance
