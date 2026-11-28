#pragma once

// Small reusable widgets: status pills, score bars, painted playing cards,
// a drag-and-drop image picker, an aspect-preserving image view, a latency
// sparkline, and layout helpers for the rounded "card" panels.

#include <QFrame>
#include <QImage>
#include <QJsonValue>
#include <QLabel>
#include <QPixmap>
#include <QString>
#include <QVector>
#include <QWidget>

#include <optional>

class QPainter;
class QTreeWidget;
class QTreeWidgetItem;
class QVBoxLayout;

enum class Tone { Neutral, Accent, Success, Warning, Danger, Info };
QColor toneColor(Tone t);

// ---- formatting --------------------------------------------------------
QString fmtAmount(double v);
QString fmtAmount(const QJsonValue& v, const QString& missing = QStringLiteral("—"));
QString fmtBytes(qint64 n);
QString fmtPercent(double v);  // 0.873 -> "87.3%"
QString prettyJson(const QByteArray& body);

// ---- layout helpers ----------------------------------------------------
QLabel* makeLabel(const QString& text, const char* role = nullptr, QWidget* parent = nullptr);
// A rounded panel with an optional uppercase section title; *body receives
// the content layout.
QFrame* makePanel(const QString& title, QVBoxLayout** body, QWidget* parent = nullptr);
QFrame* makeDivider();
// Re-apply the stylesheet after a dynamic property change.
void repolish(QWidget* w);
// A page header: title + subtitle stacked.
QWidget* makePageHeader(const QString& title, const QString& subtitle, QWidget* trailing = nullptr);

// Fill a tree with a JSON value: objects/arrays expand, scalars show value.
void fillJsonTree(QTreeWidget* tree, const QJsonValue& v);

// ---- Pill --------------------------------------------------------------
class Pill : public QWidget {
  Q_OBJECT
 public:
  explicit Pill(const QString& text = {}, Tone tone = Tone::Neutral, QWidget* parent = nullptr);
  void set(const QString& text, Tone tone);
  void setText(const QString& text);
  void setTone(Tone tone);
  void setDot(bool dot) { dot_ = dot; update(); }
  QString text() const { return text_; }
  QSize sizeHint() const override;
  QSize minimumSizeHint() const override { return sizeHint(); }

 protected:
  void paintEvent(QPaintEvent*) override;

 private:
  QString text_;
  Tone tone_;
  bool dot_ = true;
};

// ---- ScoreBar ----------------------------------------------------------
class ScoreBar : public QWidget {
  Q_OBJECT
 public:
  explicit ScoreBar(const QString& label = {}, QWidget* parent = nullptr);
  // value/max in [0, max]; text overrides the numeric caption.
  void setValue(double value, double max = 1.0, const QString& text = {});
  void setLabel(const QString& label) { label_ = label; update(); }
  void setHighlight(bool h) { highlight_ = h; update(); }
  void setThreshold(std::optional<double> t) { threshold_ = t; update(); }
  QSize sizeHint() const override { return {240, 34}; }

 protected:
  void paintEvent(QPaintEvent*) override;

 private:
  QString label_, text_;
  double value_ = 0, max_ = 1;
  bool highlight_ = false;
  std::optional<double> threshold_;
};

// ---- Playing cards -----------------------------------------------------
// id: "Ah", "Td", "10c", "covered" (card back), "" (empty slot), "?" (unknown).
void paintCard(QPainter& p, const QRectF& r, const QString& id, bool ghost = false);
QColor suitColor(QChar suit);
QString suitGlyph(QChar suit);

class CardWidget : public QWidget {
  Q_OBJECT
 public:
  explicit CardWidget(QSize size = {88, 124}, QWidget* parent = nullptr);
  void setCard(const QString& id) { id_ = id; update(); }
  QSize sizeHint() const override { return size_; }

 protected:
  void paintEvent(QPaintEvent*) override;

 private:
  QSize size_;
  QString id_;
};

// ---- DropZone ----------------------------------------------------------
// Click to pick a file, or drop an image file / raw image data on it.
class DropZone : public QFrame {
  Q_OBJECT
 public:
  explicit DropZone(const QString& hint, QWidget* parent = nullptr);
  bool hasImage() const { return !bytes_.isEmpty(); }
  QByteArray bytes() const { return bytes_; }
  QString fileName() const { return name_; }
  QImage image() const { return image_; }
  bool loadFile(const QString& path);
  void setImageBytes(const QByteArray& bytes, const QString& name);
  void clear();
  QSize sizeHint() const override { return {420, 260}; }

 Q_SIGNALS:
  void imageChanged();

 public Q_SLOTS:
  void browse();

 protected:
  void paintEvent(QPaintEvent*) override;
  void mousePressEvent(QMouseEvent*) override;
  void dragEnterEvent(QDragEnterEvent*) override;
  void dragLeaveEvent(QDragLeaveEvent*) override;
  void dropEvent(QDropEvent*) override;

 private:
  QString hint_, name_;
  QByteArray bytes_;
  QImage image_;
  bool hover_ = false;
};

// ---- ImageView ---------------------------------------------------------
// Aspect-fit image with a placeholder; reports clicks in IMAGE coordinates.
class ImageView : public QWidget {
  Q_OBJECT
 public:
  explicit ImageView(const QString& placeholder, QWidget* parent = nullptr);
  void setImage(const QImage& img);
  void setPlaceholder(const QString& text) { placeholder_ = text; update(); }
  QImage image() const { return image_; }
  QSize sizeHint() const override { return {480, 300}; }

 Q_SIGNALS:
  void pointPicked(QPoint imagePoint);

 protected:
  void paintEvent(QPaintEvent*) override;
  void mouseMoveEvent(QMouseEvent*) override;
  void mousePressEvent(QMouseEvent*) override;
  void leaveEvent(QEvent*) override;

 private:
  QRectF imageRect() const;
  std::optional<QPoint> toImage(QPointF widgetPos) const;
  QImage image_;
  QString placeholder_;
  std::optional<QPoint> hover_;
  std::optional<QPoint> marker_;
};

// ---- Sparkline ---------------------------------------------------------
class Sparkline : public QWidget {
  Q_OBJECT
 public:
  explicit Sparkline(QWidget* parent = nullptr);
  void push(double v);  // NaN = a failed sample (drawn as a gap marker)
  void setCapacity(int n) { cap_ = n; }
  QSize sizeHint() const override { return {320, 70}; }

 protected:
  void paintEvent(QPaintEvent*) override;

 private:
  QVector<double> values_;
  int cap_ = 60;
};
