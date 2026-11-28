#include "tableview.h"

#include <QJsonArray>
#include <QPainter>
#include <QPainterPath>
#include <QRadialGradient>

#include <cmath>
#include <numbers>

#include "theme.h"
#include "widgets.h"

namespace {

std::optional<double> optNum(const QJsonObject& o, const char* key) {
  const QJsonValue v = o.value(QLatin1String(key));
  if (v.isDouble()) return v.toDouble();
  return std::nullopt;
}

QStringList strList(const QJsonValue& v) {
  QStringList out;
  for (const auto& e : v.toArray()) out << e.toString();
  return out;
}

QFont uiFont(const QFont& base, int px, QFont::Weight w = QFont::Normal) {
  QFont f = base;
  f.setPixelSize(std::max(7, px));
  f.setWeight(w);
  return f;
}

}  // namespace

TableView::TableView(QWidget* parent) : QWidget(parent) {
  setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
  clearState(tr("No table state yet"), tr("Connect to a server and capture a screenshot"));
}

void TableView::clearState(const QString& message, const QString& detail) {
  has_ = false;
  message_ = message;
  detail_ = detail;
  update();
}

void TableView::setState(const QJsonObject& s) {
  has_ = true;
  maxPlayers_ = std::clamp(s.value(QStringLiteral("max_players")).toInt(6), 2, 10);
  seats_.clear();
  for (const auto& sv : s.value(QStringLiteral("seats")).toArray()) {
    const QJsonObject so = sv.toObject();
    Seat seat;
    seat.index = so.value(QStringLiteral("index")).toInt();
    seat.cards = strList(so.value(QStringLiteral("cards")));
    seat.stack = optNum(so, "stack");
    seat.bet = optNum(so, "bet");
    seat.inHand = so.value(QStringLiteral("in_hand")).toBool() || !seat.cards.isEmpty();
    seats_.push_back(seat);
  }
  maxPlayers_ = std::max<int>(maxPlayers_, seats_.size());
  dealer_ = s.value(QStringLiteral("dealer")).toInt(0);
  pot_ = optNum(s, "pot");
  call_ = optNum(s, "call");
  raise_ = optNum(s, "raise");
  stage_ = s.value(QStringLiteral("stage")).toString();
  board_ = strList(s.value(QStringLiteral("board")));
  myTurn_ = s.value(QStringLiteral("my_turn")).toBool();
  flagged_.clear();
  const QJsonObject val = s.value(QStringLiteral("validation")).toObject();
  for (const auto& e : val.value(QStringLiteral("errors")).toArray())
    for (const auto& sl : e.toObject().value(QStringLiteral("slots")).toArray()) flagged_.insert(sl.toString());
  update();
}

void TableView::paintEvent(QPaintEvent*) {
  QPainter p(this);
  p.setRenderHint(QPainter::Antialiasing);
  p.setRenderHint(QPainter::TextAntialiasing);
  const ThemeColors& c = Theme::colors();

  // Fit a 2:1 table into the widget leaving room for seat plates.
  const QRectF area = QRectF(rect()).adjusted(90, 64, -90, -78);
  // Prefer a 2:1 stadium but let tall widgets grow the table vertically.
  const qreal aspect = std::clamp(area.width() / std::max<qreal>(1, area.height()), 1.55, 2.05);
  qreal w = area.width(), h = area.width() / aspect;
  if (h > area.height()) {
    h = area.height();
    w = h * aspect;
  }
  const QRectF table(area.center().x() - w / 2, area.center().y() - h / 2, w, h);
  const qreal scale = std::clamp(w / 700.0, 0.70, 1.35);
  const QPointF ctr = table.center();

  // Rail (outer) + felt (inner), stadium shaped.
  const qreal railW = 16 * scale;
  const QRectF railR = table.adjusted(-railW, -railW, railW, railW);
  p.setPen(Qt::NoPen);
  p.setBrush(QColor(0, 0, 0, 60));
  p.drawRoundedRect(railR.translated(0, 8 * scale), railR.height() / 2, railR.height() / 2);
  QLinearGradient rg(railR.topLeft(), railR.bottomLeft());
  rg.setColorAt(0, c.railEdge);
  rg.setColorAt(0.08, c.rail);
  rg.setColorAt(1, c.rail.darker(130));
  p.setBrush(rg);
  p.drawRoundedRect(railR, railR.height() / 2, railR.height() / 2);
  QRadialGradient fg(ctr, w * 0.6);
  fg.setColorAt(0, c.feltInner.lighter(108));
  fg.setColorAt(0.7, c.feltInner);
  fg.setColorAt(1, c.feltOuter);
  p.setBrush(fg);
  p.setPen(QPen(QColor(0, 0, 0, 90), 2));
  p.drawRoundedRect(table, h / 2, h / 2);
  // Inner betting line.
  const QRectF line = table.adjusted(w * 0.07, h * 0.14, -w * 0.07, -h * 0.14);
  p.setPen(QPen(QColor(255, 255, 255, 28), 1.4));
  p.setBrush(Qt::NoBrush);
  p.drawRoundedRect(line, line.height() / 2, line.height() / 2);

  if (!has_) {
    p.setPen(QColor(255, 255, 255, 220));
    p.setFont(uiFont(font(), int(18 * scale), QFont::DemiBold));
    p.drawText(QRectF(table.left(), ctr.y() - 30 * scale, w, 28 * scale), Qt::AlignCenter, message_);
    p.setPen(QColor(255, 255, 255, 130));
    p.setFont(uiFont(font(), int(13 * scale)));
    p.drawText(QRectF(table.left(), ctr.y() + 2 * scale, w, 22 * scale), Qt::AlignCenter, detail_);
    // Ghost board.
    const QSizeF cs(40 * scale, 56 * scale);
    const qreal gap = 8 * scale;
    const qreal bx = ctr.x() - (5 * cs.width() + 4 * gap) / 2;
    for (int i = 0; i < 5; ++i)
      paintCard(p, QRectF(QPointF(bx + i * (cs.width() + gap), ctr.y() + 36 * scale), cs), QString(), true);
    return;
  }

  // ---- board, pot, stage
  const QSizeF cs(46 * scale, 64 * scale);
  const qreal gap = 8 * scale;
  const qreal bw = 5 * cs.width() + 4 * gap;
  const qreal by = ctr.y() - cs.height() / 2 + 6 * scale;
  for (int i = 0; i < 5; ++i) {
    const QRectF cr(QPointF(ctr.x() - bw / 2 + i * (cs.width() + gap), by), cs);
    paintCard(p, cr, i < board_.size() ? board_[i] : QString());
    if (flagged_.contains(QStringLiteral("board%1").arg(i + 1))) {
      p.setPen(QPen(c.danger, 2.2));
      p.setBrush(Qt::NoBrush);
      p.drawRoundedRect(cr.adjusted(-3, -3, 3, 3), 7, 7);
    }
  }
  // Pot pill above the board.
  {
    const QString t = pot_ ? tr("Pot  %1").arg(fmtAmount(*pot_)) : tr("Pot  —");
    const QFont f = uiFont(font(), int(13 * scale), QFont::DemiBold);
    const qreal tw = QFontMetricsF(f).horizontalAdvance(t) + 26 * scale;
    const QRectF pr(ctr.x() - tw / 2, by - 36 * scale, tw, 24 * scale);
    p.setPen(Qt::NoPen);
    p.setBrush(QColor(0, 0, 0, 110));
    p.drawRoundedRect(pr, pr.height() / 2, pr.height() / 2);
    p.setFont(f);
    p.setPen(QColor(255, 255, 255, 235));
    p.drawText(pr, Qt::AlignCenter, t);
  }
  // Stage under the board.
  {
    const QString t = stage_.isEmpty() ? tr("NO STAGE") : stage_.toUpper();
    QFont f = uiFont(font(), int(11 * scale), QFont::Bold);
    f.setLetterSpacing(QFont::AbsoluteSpacing, 2.2 * scale);
    p.setFont(f);
    p.setPen(QColor(255, 255, 255, 140));
    p.drawText(QRectF(table.left(), by + cs.height() + 8 * scale, w, 18 * scale), Qt::AlignCenter, t);
  }

  // ---- seats
  QHash<int, Seat> byIndex;
  for (const Seat& s : seats_) byIndex.insert(s.index, s);
  const qreal rx = w / 2 + railW * 0.4, ry = h / 2 + railW * 0.4;
  for (int i = 0; i < maxPlayers_; ++i) {
    const qreal th = std::numbers::pi / 2 + i * 2 * std::numbers::pi / maxPlayers_;
    // Stadium-ish placement: push points out along the flat sides.
    // Ellipse placement, nudged outward toward the stadium's corners.
    const qreal cx = std::cos(th), cy = std::sin(th);
    const qreal corner = std::abs(cx * cy) * 0.35;
    const QPointF at(ctr.x() + rx * cx * (1.0 + corner * 0.3), ctr.y() + ry * cy * (1.0 + corner));
    const int idx = i + 1;
    Seat s = byIndex.value(idx);
    s.index = idx;
    paintSeat(p, s, at, ctr, dealer_ == idx, idx == 1, scale);
  }
}

void TableView::paintSeat(QPainter& p, const Seat& s, QPointF at, QPointF center, bool dealer, bool hero,
                          qreal scale) {
  const ThemeColors& c = Theme::colors();
  const bool seated = s.stack.has_value() || s.inHand || !s.cards.isEmpty() || s.bet.has_value();
  const QSizeF ps(132 * scale, 50 * scale);
  const QRectF plate(at - QPointF(ps.width() / 2, ps.height() / 2), ps);
  const QPointF toC = center - at;
  const qreal dist = std::hypot(toC.x(), toC.y());
  const QPointF dir = dist > 0 ? toC / dist : QPointF(0, -1);

  // Hole cards: tucked behind the plate, toward the table centre.
  if (!s.cards.isEmpty()) {
    const QSizeF cs(34 * scale, 48 * scale);
    // Along the seat->centre direction, clear of the plate (ellipse-ish
    // extent of the plate in that direction).
    const qreal reach = std::hypot(dir.x() * ps.width() * 0.40, dir.y() * ps.height() * 0.5);
    const QPointF cc = at + dir * (reach + cs.height() * 0.42);
    const int n = s.cards.size();
    const qreal spread = 26 * scale;
    for (int i = 0; i < n; ++i) {
      const qreal off = (i - (n - 1) / 2.0) * spread;
      p.save();
      p.translate(cc + QPointF(off, 0));
      p.rotate((i - (n - 1) / 2.0) * 7);
      paintCard(p, QRectF(-cs.width() / 2, -cs.height() / 2, cs.width(), cs.height()), s.cards[i]);
      p.restore();
    }
  }

  // Plate.
  if (hero && myTurn_) {
    for (int g = 4; g >= 1; --g) {
      QColor glow = c.accent;
      glow.setAlpha(28 * g / 2);
      p.setPen(Qt::NoPen);
      p.setBrush(glow);
      const qreal e = (5 - g) * 3 * scale;
      p.drawRoundedRect(plate.adjusted(-e, -e, e, e), ps.height() / 2 + e, ps.height() / 2 + e);
    }
  }
  p.setPen(QPen(hero && myTurn_ ? c.accent : QColor(255, 255, 255, seated ? 40 : 18), hero && myTurn_ ? 2 : 1));
  QColor plateBg = seated ? QColor(0x12, 0x15, 0x1b, 240) : QColor(0x12, 0x15, 0x1b, 140);
  p.setBrush(plateBg);
  p.drawRoundedRect(plate, ps.height() / 2, ps.height() / 2);

  // Avatar circle with seat number.
  const qreal av = ps.height() - 12 * scale;
  const QRectF avR(plate.left() + 6 * scale, plate.top() + 6 * scale, av, av);
  p.setPen(Qt::NoPen);
  p.setBrush(hero ? c.accent : (seated ? QColor(0x2c, 0x33, 0x40) : QColor(0x20, 0x25, 0x2e)));
  p.drawEllipse(avR);
  p.setPen(hero ? QColor(Qt::white) : QColor(255, 255, 255, seated ? 210 : 90));
  p.setFont(uiFont(font(), int(13 * scale), QFont::Bold));
  p.drawText(avR, Qt::AlignCenter, QString::number(s.index));

  const QRectF txt(avR.right() + 8 * scale, plate.top() + 5 * scale, plate.right() - avR.right() - 18 * scale,
                   ps.height() - 10 * scale);
  if (seated && s.inHand) {
    // In-hand marker on the avatar.
    p.setPen(QPen(QColor(0x12, 0x15, 0x1b), 2));
    p.setBrush(c.success);
    p.drawEllipse(QPointF(avR.right() - 3 * scale, avR.top() + 4 * scale), 4.5 * scale, 4.5 * scale);
  }
  p.setFont(uiFont(font(), int(10.5 * scale), QFont::DemiBold));
  p.setPen(QColor(255, 255, 255, 120));
  QString label = hero ? tr("HERO") : tr("SEAT %1").arg(s.index);
  if (!seated) label += tr(" · EMPTY");
  p.drawText(QRectF(txt.left(), txt.top(), txt.width(), txt.height() / 2), Qt::AlignLeft | Qt::AlignVCenter,
             label);
  p.setFont(uiFont(font(), int(15 * scale), QFont::Bold));
  p.setPen(seated ? QColor(255, 255, 255, 240) : QColor(255, 255, 255, 80));
  p.drawText(QRectF(txt.left(), txt.center().y() - 2 * scale, txt.width(), txt.height() / 2 + 2 * scale),
             Qt::AlignLeft | Qt::AlignVCenter, s.stack ? fmtAmount(*s.stack) : QStringLiteral("—"));

  if (hero && myTurn_) {
    const QString t = tr("YOUR TURN");
    QFont f = uiFont(font(), int(10 * scale), QFont::Bold);
    f.setLetterSpacing(QFont::AbsoluteSpacing, 1.2 * scale);
    const qreal tw = QFontMetricsF(f).horizontalAdvance(t) + 16 * scale;
    const QRectF tag(plate.center().x() - tw / 2, plate.bottom() + 6 * scale, tw, 18 * scale);
    p.setPen(Qt::NoPen);
    p.setBrush(c.accent);
    p.drawRoundedRect(tag, tag.height() / 2, tag.height() / 2);
    p.setFont(f);
    p.setPen(Qt::white);
    p.drawText(tag, Qt::AlignCenter, t);
  }

  // Dealer button: beside the plate, toward the centre.
  if (dealer) {
    const qreal r = 11 * scale;
    const QPointF side(-dir.y(), dir.x());
    QPointF dp = at + dir * (ps.height() * 0.5 + 16 * scale) + side * (ps.width() * 0.5 + 6 * scale);
    p.setPen(QPen(QColor(0, 0, 0, 60), 1));
    p.setBrush(QColor(0xf7, 0xf7, 0xf2));
    p.drawEllipse(dp, r, r);
    p.setPen(QColor(0x1c, 0x20, 0x29));
    p.setFont(uiFont(font(), int(11 * scale), QFont::Black));
    p.drawText(QRectF(dp.x() - r, dp.y() - r, 2 * r, 2 * r), Qt::AlignCenter, QStringLiteral("D"));
  }

  // Bet chip stack: between the seat and the centre.
  if (s.bet && *s.bet > 0) {
    const QPointF bp = at + dir * (dist * 0.56);
    const qreal r = 8 * scale;
    const QColor chip = hero ? c.accent : c.warning;
    for (int i = 2; i >= 0; --i) {
      const QPointF cp = bp + QPointF(-14 * scale, -i * 3 * scale);
      p.setPen(QPen(chip.darker(140), 1));
      p.setBrush(chip);
      p.drawEllipse(cp, r, r * 0.8);
    }
    p.setPen(QPen(QColor(255, 255, 255, 170), 1.2, Qt::DashLine));
    p.setBrush(Qt::NoBrush);
    p.drawEllipse(bp + QPointF(-14 * scale, -6 * scale), r * 0.6, r * 0.45);
    const QString t = fmtAmount(*s.bet);
    const QFont f = uiFont(font(), int(12 * scale), QFont::Bold);
    const qreal tw = QFontMetricsF(f).horizontalAdvance(t) + 14 * scale;
    const QRectF betR(bp.x() - 2 * scale, bp.y() - 10 * scale, tw, 20 * scale);
    p.setPen(Qt::NoPen);
    p.setBrush(QColor(0, 0, 0, 120));
    p.drawRoundedRect(betR, betR.height() / 2, betR.height() / 2);
    p.setFont(f);
    p.setPen(Qt::white);
    p.drawText(betR, Qt::AlignCenter, t);
  }
}
