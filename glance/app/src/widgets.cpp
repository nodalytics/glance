#include "widgets.h"

#include <QBuffer>
#include <QDragEnterEvent>
#include <QFileDialog>
#include <QFileInfo>
#include <QHBoxLayout>
#include <QImageReader>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLocale>
#include <QMimeData>
#include <QPainter>
#include <QPainterPath>
#include <QStyle>
#include <QTreeWidget>
#include <QVBoxLayout>

#include <cmath>

#include "theme.h"

// ---------------------------------------------------------------- helpers

QColor toneColor(Tone t) {
  const ThemeColors& c = Theme::colors();
  switch (t) {
    case Tone::Accent: return c.accent;
    case Tone::Success: return c.success;
    case Tone::Warning: return c.warning;
    case Tone::Danger: return c.danger;
    case Tone::Info: return c.info;
    case Tone::Neutral: break;
  }
  return c.muted;
}

QString fmtAmount(double v) {
  QLocale loc(QLocale::English);
  if (std::abs(v - std::round(v)) < 1e-9) return loc.toString(static_cast<qlonglong>(std::llround(v)));
  return loc.toString(v, 'f', 2);
}

QString fmtAmount(const QJsonValue& v, const QString& missing) {
  return v.isDouble() ? fmtAmount(v.toDouble()) : missing;
}

QString fmtBytes(qint64 n) {
  if (n < 1024) return QStringLiteral("%1 B").arg(n);
  if (n < 1024 * 1024) return QStringLiteral("%1 KB").arg(n / 1024.0, 0, 'f', 1);
  return QStringLiteral("%1 MB").arg(n / (1024.0 * 1024.0), 0, 'f', 2);
}

QString fmtPercent(double v) { return QStringLiteral("%1%").arg(v * 100.0, 0, 'f', 1); }

QString prettyJson(const QByteArray& body) {
  QJsonParseError pe;
  const QJsonDocument d = QJsonDocument::fromJson(body, &pe);
  if (pe.error == QJsonParseError::NoError) return QString::fromUtf8(d.toJson(QJsonDocument::Indented));
  return QString::fromUtf8(body);
}

QLabel* makeLabel(const QString& text, const char* role, QWidget* parent) {
  auto* l = new QLabel(text, parent);
  if (role) l->setProperty("role", QString::fromLatin1(role));
  return l;
}

QFrame* makePanel(const QString& title, QVBoxLayout** body, QWidget* parent) {
  auto* f = new QFrame(parent);
  f->setProperty("card", true);
  auto* v = new QVBoxLayout(f);
  v->setContentsMargins(18, 16, 18, 18);
  v->setSpacing(12);
  if (!title.isEmpty()) v->addWidget(makeLabel(title.toUpper(), "section"));
  if (body) *body = v;
  return f;
}

QFrame* makeDivider() {
  auto* f = new QFrame;
  f->setProperty("divider", true);
  return f;
}

void repolish(QWidget* w) {
  w->style()->unpolish(w);
  w->style()->polish(w);
  w->update();
}

QWidget* makePageHeader(const QString& title, const QString& subtitle, QWidget* trailing) {
  auto* w = new QWidget;
  auto* h = new QHBoxLayout(w);
  h->setContentsMargins(0, 0, 0, 4);
  auto* v = new QVBoxLayout;
  v->setSpacing(2);
  v->addWidget(makeLabel(title, "title"));
  v->addWidget(makeLabel(subtitle, "subtitle"));
  h->addLayout(v, 1);
  if (trailing) h->addWidget(trailing, 0, Qt::AlignBottom);
  return w;
}

namespace {

void addJson(QTreeWidgetItem* parent, QTreeWidget* tree, const QString& key, const QJsonValue& v,
             int depth) {
  auto* item = parent ? new QTreeWidgetItem(parent) : new QTreeWidgetItem(tree);
  item->setText(0, key);
  const ThemeColors& c = Theme::colors();
  if (v.isObject()) {
    const QJsonObject o = v.toObject();
    item->setText(1, QStringLiteral("{ %1 }").arg(o.size()));
    item->setForeground(1, c.faint);
    for (auto it = o.begin(); it != o.end(); ++it) addJson(item, tree, it.key(), it.value(), depth + 1);
    item->setExpanded(depth < 2);
  } else if (v.isArray()) {
    const QJsonArray a = v.toArray();
    // Short scalar arrays read better inline: ["Ah","Kd"].
    bool scalar = a.size() <= 8;
    for (const auto& e : a) scalar = scalar && !e.isObject() && !e.isArray();
    if (scalar && !a.isEmpty()) {
      item->setText(1, QString::fromUtf8(QJsonDocument(a).toJson(QJsonDocument::Compact)));
      item->setForeground(1, c.info);
    } else {
      item->setText(1, QStringLiteral("[ %1 ]").arg(a.size()));
      item->setForeground(1, c.faint);
      for (int i = 0; i < a.size(); ++i) addJson(item, tree, QString::number(i), a.at(i), depth + 1);
      item->setExpanded(depth < 2);
    }
  } else if (v.isString()) {
    item->setText(1, QStringLiteral("\"%1\"").arg(v.toString()));
    item->setForeground(1, c.success);
  } else if (v.isDouble()) {
    item->setText(1, QString::number(v.toDouble(), 'g', 10));
    item->setForeground(1, c.accent);
  } else if (v.isBool()) {
    item->setText(1, v.toBool() ? QStringLiteral("true") : QStringLiteral("false"));
    item->setForeground(1, c.warning);
  } else {
    item->setText(1, QStringLiteral("null"));
    item->setForeground(1, c.faint);
  }
  item->setForeground(0, c.muted);
}

}  // namespace

void fillJsonTree(QTreeWidget* tree, const QJsonValue& v) {
  tree->clear();
  if (v.isObject()) {
    const QJsonObject o = v.toObject();
    for (auto it = o.begin(); it != o.end(); ++it) addJson(nullptr, tree, it.key(), it.value(), 0);
  } else if (v.isArray()) {
    const QJsonArray a = v.toArray();
    for (int i = 0; i < a.size(); ++i) addJson(nullptr, tree, QString::number(i), a.at(i), 0);
  } else if (!v.isUndefined()) {
    addJson(nullptr, tree, QStringLiteral("value"), v, 0);
  }
}

// ---------------------------------------------------------------- Pill

Pill::Pill(const QString& text, Tone tone, QWidget* parent) : QWidget(parent), text_(text), tone_(tone) {
  setSizePolicy(QSizePolicy::Fixed, QSizePolicy::Fixed);
}

void Pill::set(const QString& text, Tone tone) {
  text_ = text;
  tone_ = tone;
  updateGeometry();
  update();
}
void Pill::setText(const QString& text) { set(text, tone_); }
void Pill::setTone(Tone tone) { set(text_, tone); }

QSize Pill::sizeHint() const {
  QFont f = font();
  f.setPixelSize(12);
  f.setWeight(QFont::DemiBold);
  const int w = QFontMetrics(f).horizontalAdvance(text_) + (dot_ ? 30 : 20);
  return {w, 24};
}

void Pill::paintEvent(QPaintEvent*) {
  QPainter p(this);
  p.setRenderHint(QPainter::Antialiasing);
  const QColor tc = toneColor(tone_);
  const ThemeColors& c = Theme::colors();
  const QRectF r = QRectF(rect()).adjusted(0.5, 0.5, -0.5, -0.5);
  const bool dark = Theme::mode() == Theme::Mode::Dark;
  QColor bg = tone_ == Tone::Neutral ? c.surface2 : Theme::soft(tc, dark ? 0.18 : 0.12);
  QColor line = tone_ == Tone::Neutral ? c.border : Theme::soft(tc, dark ? 0.40 : 0.32);
  p.setPen(QPen(line, 1));
  p.setBrush(bg);
  p.drawRoundedRect(r, r.height() / 2, r.height() / 2);
  int x = 10;
  if (dot_) {
    p.setPen(Qt::NoPen);
    p.setBrush(tc);
    p.drawEllipse(QPointF(x + 3, r.center().y()), 3.2, 3.2);
    x += 12;
  }
  QFont f = font();
  f.setPixelSize(12);
  f.setWeight(QFont::DemiBold);
  p.setFont(f);
  p.setPen(tone_ == Tone::Neutral ? c.muted : tc);
  p.drawText(QRectF(x, 0, width() - x - 8, height()), Qt::AlignVCenter | Qt::AlignLeft, text_);
}

// ---------------------------------------------------------------- ScoreBar

ScoreBar::ScoreBar(const QString& label, QWidget* parent) : QWidget(parent), label_(label) {
  setMinimumHeight(34);
  setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);
}

void ScoreBar::setValue(double value, double max, const QString& text) {
  value_ = value;
  max_ = max <= 0 ? 1 : max;
  text_ = text;
  update();
}

void ScoreBar::paintEvent(QPaintEvent*) {
  QPainter p(this);
  p.setRenderHint(QPainter::Antialiasing);
  const ThemeColors& c = Theme::colors();
  QFont f = font();
  f.setPixelSize(12);
  p.setFont(f);
  const QString caption = text_.isEmpty() ? QString::number(value_, 'f', 3) : text_;
  p.setPen(highlight_ ? c.text : c.muted);
  if (highlight_) {
    QFont b = f;
    b.setWeight(QFont::DemiBold);
    p.setFont(b);
  }
  p.drawText(QRectF(0, 0, width(), 18), Qt::AlignLeft | Qt::AlignVCenter, label_);
  p.setPen(highlight_ ? c.text : c.muted);
  QFont mono = f;
  mono.setFamilies({QStringLiteral("JetBrains Mono"), QStringLiteral("DejaVu Sans Mono"),
                    QStringLiteral("monospace")});
  mono.setPixelSize(12);
  p.setFont(mono);
  p.drawText(QRectF(0, 0, width(), 18), Qt::AlignRight | Qt::AlignVCenter, caption);

  const QRectF track(0, 23, width(), 7);
  p.setPen(Qt::NoPen);
  p.setBrush(c.surface2);
  p.drawRoundedRect(track, 3.5, 3.5);
  const double frac = std::clamp(value_ / max_, 0.0, 1.0);
  if (frac > 0) {
    QRectF fill = track;
    fill.setWidth(std::max(7.0, track.width() * frac));
    QLinearGradient g(fill.topLeft(), fill.topRight());
    const QColor base = highlight_ ? c.success : c.accent;
    g.setColorAt(0, base.darker(115));
    g.setColorAt(1, base);
    p.setBrush(g);
    p.drawRoundedRect(fill, 3.5, 3.5);
  }
  if (threshold_) {
    const double tx = track.left() + track.width() * std::clamp(*threshold_ / max_, 0.0, 1.0);
    p.setPen(QPen(c.warning, 2));
    p.drawLine(QPointF(tx, track.top() - 3), QPointF(tx, track.bottom() + 3));
  }
}

// ---------------------------------------------------------------- cards

QColor suitColor(QChar s) {
  switch (s.toLower().unicode()) {
    case 'h': return QColor(0xe0, 0x36, 0x4d);
    case 'd': return QColor(0x2f, 0x7f, 0xe0);
    case 'c': return QColor(0x1e, 0x9a, 0x56);
    case 's': return QColor(0x1c, 0x20, 0x29);
    default: return QColor(0x6b, 0x72, 0x80);
  }
}

QString suitGlyph(QChar s) {
  switch (s.toLower().unicode()) {
    case 'h': return QString(QChar(0x2665));
    case 'd': return QString(QChar(0x2666));
    case 'c': return QString(QChar(0x2663));
    case 's': return QString(QChar(0x2660));
    default: return QStringLiteral("?");
  }
}

void paintCard(QPainter& p, const QRectF& r, const QString& id, bool ghost) {
  const ThemeColors& c = Theme::colors();
  p.save();
  p.setRenderHint(QPainter::Antialiasing);
  p.setRenderHint(QPainter::TextAntialiasing);
  const qreal rad = std::max<qreal>(3.0, r.width() * 0.12);

  if (id.isEmpty()) {
    QPen pen(QColor(255, 255, 255, ghost ? 40 : 70), 1.2, Qt::DashLine);
    p.setPen(pen);
    p.setBrush(QColor(255, 255, 255, 12));
    p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), rad, rad);
    p.restore();
    return;
  }

  // Drop shadow.
  p.setPen(Qt::NoPen);
  p.setBrush(QColor(0, 0, 0, 70));
  p.drawRoundedRect(r.translated(0, std::max<qreal>(1.5, r.height() * 0.03)), rad, rad);

  if (id == QLatin1String("covered")) {
    QLinearGradient g(r.topLeft(), r.bottomRight());
    g.setColorAt(0, c.cardBackAlt);
    g.setColorAt(1, c.cardBack);
    p.setBrush(g);
    p.setPen(QPen(QColor(255, 255, 255, 200), std::max<qreal>(1.2, r.width() * 0.04)));
    p.drawRoundedRect(r, rad, rad);
    const QRectF inner = r.adjusted(r.width() * 0.14, r.width() * 0.14, -r.width() * 0.14,
                                    -r.width() * 0.14);
    QPainterPath clip;
    clip.addRoundedRect(inner, rad * 0.6, rad * 0.6);
    p.setClipPath(clip);
    p.setPen(QPen(QColor(255, 255, 255, 45), 1));
    const qreal step = std::max<qreal>(4.0, r.width() * 0.12);
    for (qreal x = inner.left() - inner.height(); x < inner.right(); x += step) {
      p.drawLine(QPointF(x, inner.bottom()), QPointF(x + inner.height(), inner.top()));
      p.drawLine(QPointF(x, inner.top()), QPointF(x + inner.height(), inner.bottom()));
    }
    p.setClipping(false);
    p.setPen(QPen(QColor(255, 255, 255, 90), 1));
    p.setBrush(Qt::NoBrush);
    p.drawRoundedRect(inner, rad * 0.6, rad * 0.6);
    p.restore();
    return;
  }

  QString rank;
  QChar suit;
  if (id.size() >= 2) {
    const QChar last = id.back().toLower();
    if (QStringLiteral("hdcs").contains(last)) {
      suit = last;
      rank = id.left(id.size() - 1).toUpper();
      if (rank == QLatin1String("T")) rank = QStringLiteral("10");
    }
  }

  p.setBrush(c.cardFace);
  p.setPen(QPen(QColor(0, 0, 0, 40), 1));
  p.drawRoundedRect(r, rad, rad);

  QFont f = p.font();
  f.setFamilies({QStringLiteral("Inter"), QStringLiteral("Cantarell"), QStringLiteral("Noto Sans"),
                 QStringLiteral("DejaVu Sans")});
  f.setWeight(QFont::Bold);
  if (suit.isNull()) {
    f.setPixelSize(std::max(8, int(r.height() * 0.34)));
    p.setFont(f);
    p.setPen(QColor(0x6b, 0x72, 0x80));
    const QString label = id == QLatin1String("?") ? id : id.left(4);
    p.drawText(r, Qt::AlignCenter, label);
    p.restore();
    return;
  }
  const QColor sc = suitColor(suit);
  p.setPen(sc);
  const bool tiny = r.height() < 60;
  f.setPixelSize(std::max(8, int(r.height() * (tiny ? 0.36 : 0.26))));
  f.setLetterSpacing(QFont::PercentageSpacing, rank.size() > 1 ? 90 : 100);
  p.setFont(f);
  const qreal pad = r.width() * 0.10;
  const QRectF rankBox(r.left() + pad, r.top() + pad * 0.6, r.width() - 2 * pad, r.height() * 0.40);
  p.drawText(rankBox, Qt::AlignLeft | Qt::AlignTop, rank);

  QFont g = f;
  g.setFamilies({QStringLiteral("DejaVu Sans"), QStringLiteral("Noto Sans Symbols2"),
                 QStringLiteral("Noto Sans")});
  g.setLetterSpacing(QFont::PercentageSpacing, 100);
  if (tiny) {
    g.setPixelSize(std::max(8, int(r.height() * 0.42)));
    p.setFont(g);
    p.drawText(r.adjusted(pad, 0, -pad * 0.6, -pad * 0.2), Qt::AlignRight | Qt::AlignBottom,
               suitGlyph(suit));
  } else {
    g.setPixelSize(std::max(8, int(r.height() * 0.17)));
    p.setFont(g);
    const QFontMetricsF fm(f);
    p.drawText(QRectF(r.left() + pad, r.top() + pad * 0.6 + fm.height() * 0.92, r.width(), r.height()),
               Qt::AlignLeft | Qt::AlignTop, suitGlyph(suit));
    g.setPixelSize(std::max(8, int(r.height() * 0.46)));
    p.setFont(g);
    p.drawText(r.adjusted(0, r.height() * 0.22, -pad * 0.6, -pad * 0.1),
               Qt::AlignRight | Qt::AlignBottom, suitGlyph(suit));
  }
  p.restore();
}

CardWidget::CardWidget(QSize size, QWidget* parent) : QWidget(parent), size_(size) {
  setFixedSize(size);
}

void CardWidget::paintEvent(QPaintEvent*) {
  QPainter p(this);
  const QRectF r = QRectF(rect()).adjusted(1, 1, -1, -4);
  if (id_.isEmpty()) {
    const ThemeColors& c = Theme::colors();
    p.setRenderHint(QPainter::Antialiasing);
    p.setPen(QPen(c.borderStrong, 1.2, Qt::DashLine));
    p.setBrush(c.surface2);
    p.drawRoundedRect(r, 10, 10);
    p.setPen(c.faint);
    QFont f = font();
    f.setPixelSize(int(r.height() * 0.3));
    p.setFont(f);
    p.drawText(r, Qt::AlignCenter, QStringLiteral("?"));
    return;
  }
  paintCard(p, r, id_);
}

// ---------------------------------------------------------------- DropZone

DropZone::DropZone(const QString& hint, QWidget* parent) : QFrame(parent), hint_(hint) {
  setAcceptDrops(true);
  setCursor(Qt::PointingHandCursor);
  setMinimumSize(240, 180);
  setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
}

bool DropZone::loadFile(const QString& path) {
  QFile f(path);
  if (!f.open(QIODevice::ReadOnly)) return false;
  setImageBytes(f.readAll(), QFileInfo(path).fileName());
  return true;
}

void DropZone::setImageBytes(const QByteArray& bytes, const QString& name) {
  bytes_ = bytes;
  name_ = name;
  image_ = QImage::fromData(bytes);
  update();
  Q_EMIT imageChanged();
}

void DropZone::clear() {
  bytes_.clear();
  name_.clear();
  image_ = QImage();
  update();
  Q_EMIT imageChanged();
}

void DropZone::browse() {
  const QString path = QFileDialog::getOpenFileName(
      this, tr("Choose image"), QString(), tr("Images (*.png *.jpg *.jpeg *.bmp *.webp);;All files (*)"));
  if (!path.isEmpty()) loadFile(path);
}

void DropZone::mousePressEvent(QMouseEvent* e) {
  if (e->button() == Qt::LeftButton) browse();
}

void DropZone::dragEnterEvent(QDragEnterEvent* e) {
  const QMimeData* m = e->mimeData();
  if (m->hasUrls() || m->hasImage()) {
    hover_ = true;
    update();
    e->acceptProposedAction();
  }
}

void DropZone::dragLeaveEvent(QDragLeaveEvent*) {
  hover_ = false;
  update();
}

void DropZone::dropEvent(QDropEvent* e) {
  hover_ = false;
  const QMimeData* m = e->mimeData();
  if (m->hasUrls()) {
    for (const QUrl& u : m->urls()) {
      if (u.isLocalFile() && loadFile(u.toLocalFile())) {
        e->acceptProposedAction();
        return;
      }
    }
  }
  if (m->hasImage()) {
    const QImage img = qvariant_cast<QImage>(m->imageData());
    QByteArray png;
    QBuffer buf(&png);
    buf.open(QIODevice::WriteOnly);
    img.save(&buf, "PNG");
    setImageBytes(png, tr("dropped image.png"));
    e->acceptProposedAction();
  }
  update();
}

void DropZone::paintEvent(QPaintEvent*) {
  QPainter p(this);
  p.setRenderHint(QPainter::Antialiasing);
  const ThemeColors& c = Theme::colors();
  const QRectF r = QRectF(rect()).adjusted(1, 1, -1, -1);
  p.setBrush(hover_ ? c.accentSoft : c.surface2);
  QPen pen(hover_ ? c.accent : c.borderStrong, 1.4, image_.isNull() ? Qt::DashLine : Qt::SolidLine);
  pen.setDashPattern({5, 4});
  if (!image_.isNull()) pen.setStyle(Qt::SolidLine);
  p.setPen(pen);
  p.drawRoundedRect(r, 12, 12);

  QFont f = font();
  if (image_.isNull()) {
    const QPointF ctr = r.center() - QPointF(0, 22);
    p.setPen(Qt::NoPen);
    p.setBrush(c.accentSoft);
    p.drawEllipse(ctr, 24, 24);
    p.setPen(QPen(c.accent, 2.2, Qt::SolidLine, Qt::RoundCap));
    p.drawLine(ctr + QPointF(0, -9), ctr + QPointF(0, 9));
    p.drawLine(ctr + QPointF(-9, 0), ctr + QPointF(9, 0));
    f.setPixelSize(14);
    f.setWeight(QFont::DemiBold);
    p.setFont(f);
    p.setPen(c.text);
    p.drawText(QRectF(r.left(), ctr.y() + 34, r.width(), 20), Qt::AlignCenter, hint_);
    f.setPixelSize(12);
    f.setWeight(QFont::Normal);
    p.setFont(f);
    p.setPen(c.muted);
    p.drawText(QRectF(r.left(), ctr.y() + 56, r.width(), 18), Qt::AlignCenter,
               tr("Click to browse, or drop a PNG / JPEG here"));
    return;
  }
  const QRectF area = r.adjusted(12, 12, -12, -40);
  const QSizeF s = QSizeF(image_.size()).scaled(area.size(), Qt::KeepAspectRatio);
  const QRectF target(area.center() - QPointF(s.width() / 2, s.height() / 2), s);
  p.setRenderHint(QPainter::SmoothPixmapTransform);
  QPainterPath clip;
  clip.addRoundedRect(target, 6, 6);
  p.save();
  p.setClipPath(clip);
  p.drawImage(target, image_);
  p.restore();
  f.setPixelSize(12);
  p.setFont(f);
  p.setPen(c.muted);
  p.drawText(QRectF(r.left() + 14, r.bottom() - 32, r.width() - 28, 24), Qt::AlignVCenter | Qt::AlignLeft,
             QStringLiteral("%1   ·   %2 × %3   ·   %4")
                 .arg(name_)
                 .arg(image_.width())
                 .arg(image_.height())
                 .arg(fmtBytes(bytes_.size())));
}

// ---------------------------------------------------------------- ImageView

ImageView::ImageView(const QString& placeholder, QWidget* parent)
    : QWidget(parent), placeholder_(placeholder) {
  setMouseTracking(true);
  setMinimumSize(240, 160);
  setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
}

void ImageView::setImage(const QImage& img) {
  image_ = img;
  marker_.reset();
  update();
}

QRectF ImageView::imageRect() const {
  if (image_.isNull()) return {};
  const QRectF area = QRectF(rect()).adjusted(8, 8, -8, -8);
  const QSizeF s = QSizeF(image_.size()).scaled(area.size(), Qt::KeepAspectRatio);
  return {area.center() - QPointF(s.width() / 2, s.height() / 2), s};
}

std::optional<QPoint> ImageView::toImage(QPointF pos) const {
  const QRectF ir = imageRect();
  if (ir.isEmpty() || !ir.contains(pos)) return std::nullopt;
  const double sx = image_.width() / ir.width();
  return QPoint(int((pos.x() - ir.left()) * sx), int((pos.y() - ir.top()) * sx));
}

void ImageView::mouseMoveEvent(QMouseEvent* e) {
  hover_ = toImage(e->position());
  setCursor(hover_ ? Qt::CrossCursor : Qt::ArrowCursor);
  update();
}

void ImageView::mousePressEvent(QMouseEvent* e) {
  if (auto pt = toImage(e->position()); pt && e->button() == Qt::LeftButton) {
    marker_ = pt;
    update();
    Q_EMIT pointPicked(*pt);
  }
}

void ImageView::leaveEvent(QEvent*) {
  hover_.reset();
  update();
}

void ImageView::paintEvent(QPaintEvent*) {
  QPainter p(this);
  p.setRenderHint(QPainter::Antialiasing);
  const ThemeColors& c = Theme::colors();
  const QRectF r = QRectF(rect()).adjusted(0.5, 0.5, -0.5, -0.5);
  p.setPen(QPen(c.border, 1));
  p.setBrush(c.surface2);
  p.drawRoundedRect(r, 12, 12);
  if (image_.isNull()) {
    QFont f = font();
    f.setPixelSize(13);
    p.setFont(f);
    p.setPen(c.faint);
    p.drawText(r, Qt::AlignCenter, placeholder_);
    return;
  }
  const QRectF ir = imageRect();
  p.setRenderHint(QPainter::SmoothPixmapTransform);
  p.drawImage(ir, image_);
  const double s = ir.width() / image_.width();
  auto drawMarker = [&](QPoint pt, const QColor& col, bool label) {
    const QPointF w(ir.left() + (pt.x() + 0.5) * s, ir.top() + (pt.y() + 0.5) * s);
    p.setPen(QPen(col, 1));
    p.drawLine(QPointF(ir.left(), w.y()), QPointF(ir.right(), w.y()));
    p.drawLine(QPointF(w.x(), ir.top()), QPointF(w.x(), ir.bottom()));
    p.setBrush(col);
    p.drawEllipse(w, 3, 3);
    if (!label) return;
    const QString t = QStringLiteral("%1, %2").arg(pt.x()).arg(pt.y());
    QFont f = font();
    f.setPixelSize(11);
    f.setWeight(QFont::DemiBold);
    p.setFont(f);
    const QFontMetrics fm(f);
    QRectF box(w + QPointF(10, 10), QSizeF(fm.horizontalAdvance(t) + 14, 20));
    if (box.right() > ir.right()) box.moveRight(w.x() - 10);
    if (box.bottom() > ir.bottom()) box.moveBottom(w.y() - 10);
    p.setPen(Qt::NoPen);
    p.setBrush(QColor(10, 12, 16, 220));
    p.drawRoundedRect(box, 6, 6);
    p.setPen(Qt::white);
    p.drawText(box, Qt::AlignCenter, t);
  };
  if (marker_) drawMarker(*marker_, c.warning, !hover_);
  if (hover_) drawMarker(*hover_, QColor(255, 255, 255, 150), true);
}

// ---------------------------------------------------------------- Sparkline

Sparkline::Sparkline(QWidget* parent) : QWidget(parent) {
  setMinimumHeight(56);
  setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);
}

void Sparkline::push(double v) {
  values_.push_back(v);
  while (values_.size() > cap_) values_.pop_front();
  update();
}

void Sparkline::paintEvent(QPaintEvent*) {
  QPainter p(this);
  p.setRenderHint(QPainter::Antialiasing);
  const ThemeColors& c = Theme::colors();
  const QRectF r = QRectF(rect()).adjusted(2, 6, -2, -6);
  p.setPen(QPen(c.border, 1, Qt::DotLine));
  for (int i = 0; i <= 2; ++i) {
    const qreal y = r.top() + r.height() * i / 2.0;
    p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y));
  }
  if (values_.isEmpty()) {
    p.setPen(c.faint);
    QFont f = font();
    f.setPixelSize(12);
    p.setFont(f);
    p.drawText(r, Qt::AlignCenter, tr("waiting for samples"));
    return;
  }
  double mx = 1;
  for (double v : values_)
    if (!std::isnan(v)) mx = std::max(mx, v);
  mx *= 1.15;
  const qreal step = r.width() / std::max(1, cap_ - 1);
  const qreal x0 = r.right() - step * (values_.size() - 1);
  QPainterPath line, area;
  bool open = false;
  QPointF last;
  for (int i = 0; i < values_.size(); ++i) {
    const double v = values_[i];
    const qreal x = x0 + step * i;
    if (std::isnan(v)) {
      p.setPen(Qt::NoPen);
      p.setBrush(c.danger);
      p.drawEllipse(QPointF(x, r.bottom()), 2.5, 2.5);
      open = false;
      continue;
    }
    const QPointF pt(x, r.bottom() - r.height() * (v / mx));
    if (!open) {
      line.moveTo(pt);
      open = true;
    } else {
      line.lineTo(pt);
    }
    last = pt;
  }
  area = line;
  if (!line.isEmpty()) {
    area.lineTo(QPointF(last.x(), r.bottom()));
    area.lineTo(QPointF(line.elementAt(0).x, r.bottom()));
    area.closeSubpath();
    QLinearGradient g(r.topLeft(), r.bottomLeft());
    QColor a = c.accent;
    a.setAlpha(70);
    g.setColorAt(0, a);
    a.setAlpha(0);
    g.setColorAt(1, a);
    p.setPen(Qt::NoPen);
    p.setBrush(g);
    p.drawPath(area);
    p.setBrush(Qt::NoBrush);
    p.setPen(QPen(c.accent, 1.8, Qt::SolidLine, Qt::RoundCap, Qt::RoundJoin));
    p.drawPath(line);
    p.setPen(Qt::NoPen);
    p.setBrush(c.accent);
    p.drawEllipse(last, 3, 3);
  }
}
