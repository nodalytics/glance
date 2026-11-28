#include "demo.h"

#include <QBuffer>
#include <QJsonDocument>
#include <QJsonObject>
#include <QPainter>

#include "mainwindow.h"
#include "pages.h"
#include "tableview.h"
#include "widgets.h"

namespace {

const char* kState = R"({
  "max_players": 6,
  "seats": [
    {"index": 1, "cards": ["Ah", "Kd"], "stack": 1240.5, "bet": 60, "in_hand": true},
    {"index": 2, "cards": ["covered", "covered"], "stack": 880, "bet": 120, "in_hand": true},
    {"index": 3, "stack": 2315},
    {"index": 4, "cards": ["covered", "covered"], "stack": 455.25, "in_hand": true},
    {"index": 5},
    {"index": 6, "stack": 1990, "bet": 20}
  ],
  "dealer": 4,
  "pot": 340,
  "my_turn": true,
  "call": 60,
  "raise": 240,
  "stage": "Flop",
  "board": ["Qs", "Jh", "Tc"],
  "my_cards": ["Ah", "Kd"],
  "validation": {
    "valid": true, "error_count": 0, "warning_count": 1,
    "errors": [],
    "warnings": [{"code": "bet_exceeds_stack_hint", "message": "Seat 2 bet is a large share of the visible stack.", "slots": ["p2_bet"]}]
  }
})";

const char* kHealth = R"({"status": "ok", "control": {"backend": "x11", "window": {"title": "ACR Poker", "x": 120, "y": 64}}})";

const char* kInfo = R"({
  "name": "glance", "version": "0.4.0", "ocr_available": true,
  "control": {"backend": "x11"},
  "mapping": {"name": "acr-6max", "max_players": 6, "window_title": "ACR Poker",
              "actions": {"fold": "button:fold", "check": "button:check", "call": "button:call",
                          "raise": "button:raise", "raise_bar": "stack:raise", "allin": "button:allin"}},
  "card_vision": {"configured": true, "profile": "calibration", "suit_templates": 4, "rank_templates": 13}
})";

const char* kReading = R"({
  "recognized": true, "card": "Qs", "rank": "Q", "rank_confidence": 0.912, "rank_margin": 0.184,
  "rank_source": "corner_top", "rank_verification": "confirmed",
  "suit": "spades", "suit_confidence": 0.948, "suit_margin": 0.311, "suit_source": "corner_suit:spades_arial",
  "suit_scores": {"hearts": 0.402, "diamonds": 0.281, "clubs": 0.637, "spades": 0.948},
  "suit_color": "black",
  "occupancy": {"state": "occupied", "reason": "Bright card background detected", "white_ratio": 0.71,
                "green_ratio": 0.04, "edge_ratio": 0.09, "mean_brightness": 211.4, "brightness_std": 52.7},
  "skipped": false
})";

QJsonObject obj(const char* s) { return QJsonDocument::fromJson(QByteArray(s)).object(); }

ApiResult fake(const QString& method, const QString& path, int status, const char* body, qint64 ms,
               bool quiet = false, const QByteArray& req = {}) {
  ApiResult r;
  r.method = method;
  r.path = path;
  r.url = QUrl(QStringLiteral("http://127.0.0.1:8080") + path);
  r.status = status;
  r.body = QByteArray(body);
  r.json = QJsonDocument::fromJson(r.body);
  r.contentType = QStringLiteral("application/json");
  r.elapsedMs = ms;
  r.when = QDateTime::currentDateTime();
  r.quiet = quiet;
  r.requestBody = req;
  if (status >= 400) r.error = r.json.object().value(QStringLiteral("error")).toString();
  return r;
}

QByteArray png(const QImage& img) {
  QByteArray out;
  QBuffer b(&out);
  b.open(QIODevice::WriteOnly);
  img.save(&b, "PNG");
  return out;
}

}  // namespace

void loadDemo(MainWindow& w) {
  w.setDemoMode();
  const QJsonObject state = obj(kState);

  ApiResult health = fake(QStringLiteral("GET"), QStringLiteral("/health"), 200, kHealth, 3, true);
  w.showHealth(health);
  const int lat[] = {4, 3, 5, 4, 6, 3, 3, 9, 4, 5, 4, 3, 12, 5, 4, 4, 3, 6, 4, 5, 3, 4, 7, 4, 3, 5, 4, 3};
  for (int ms : lat) {
    health.elapsedMs = ms;
    w.overview()->onHealth(health);
  }
  w.overview()->onInfo(fake(QStringLiteral("GET"), QStringLiteral("/info"), 200, kInfo, 4, true));
  w.table()->applyState(state);
  w.cardLab()->applyReading(obj(kReading));

  // A synthetic "screenshot": the painted table itself, at a desktop size.
  TableView tv;
  tv.setState(state);
  tv.resize(1100, 640);
  QImage shot(tv.size(), QImage::Format_ARGB32_Premultiplied);
  shot.fill(QColor(0x0b, 0x0e, 0x12));
  tv.render(&shot);
  w.capture()->setScreenshot(png(shot), QStringLiteral("acr_table_1100x640.png"));
  w.capture()->setFrameImage(shot, QObject::tr("Demo frame — click to pick a point for Control."));
  w.capture()->setCaptureResult(Tone::Success, QObject::tr("Table found · 38 ms"),
                                QObject::tr("Flop, 3 board card(s)"));

  QImage card(120, 168, QImage::Format_ARGB32_Premultiplied);
  card.fill(QColor(0x1c, 0x6b, 0x4c));
  {
    QPainter p(&card);
    paintCard(p, QRectF(8, 8, 104, 150), QStringLiteral("Qs"));
  }
  w.cardLab()->setCrop(png(card), QStringLiteral("board1_crop.png"));

  w.control()->setBackend(QStringLiteral("x11"));
  w.control()->setActions({QStringLiteral("fold"), QStringLiteral("check"), QStringLiteral("call"),
                           QStringLiteral("raise"), QStringLiteral("raise_bar"), QStringLiteral("allin")});
  const ApiResult log[] = {
      fake(QStringLiteral("POST"), QStringLiteral("/grab"), 200, R"({"table_found": true})", 41, false, "{}"),
      fake(QStringLiteral("POST"), QStringLiteral("/click"), 200, R"({"x": 860, "y": 729, "kind": "button", "action": "call"})", 7,
           false, R"({"action":"call"})"),
      fake(QStringLiteral("POST"), QStringLiteral("/key"), 200, "{}", 3, false, R"({"type":"240"})"),
      fake(QStringLiteral("POST"), QStringLiteral("/click"), 422, R"({"error": "unknown action 'bet'"})", 2, false,
           R"({"action":"bet"})"),
      fake(QStringLiteral("POST"), QStringLiteral("/sequence"), 200,
           R"({"steps": [{"request": {"action": "call"}, "ok": true, "detail": {"x": 860, "y": 729}}, {"request": {"key": "Return"}, "ok": true}]})",
           12, false, R"([{"action":"call"},{"key":"Return"}])"),
  };
  for (const ApiResult& r : log) {
    w.control()->logResult(r);
    w.inspector()->record(r);
  }
  w.inspector()->record(fake(QStringLiteral("GET"), QStringLiteral("/info"), 200, kInfo, 4, true));
  w.inspector()->record(health);
  ApiResult st = fake(QStringLiteral("GET"), QStringLiteral("/state"), 200, kState, 5, true);
  w.inspector()->record(st);
}
