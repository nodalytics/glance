#pragma once

// Theme tokens + the application stylesheet (dark / light).
//
// Widgets styled by QSS pick colours up automatically; custom-painted widgets
// read Theme::colors() in paintEvent and repaint on Theme::changed().

#include <QColor>
#include <QObject>
#include <QString>

struct ThemeColors {
  QColor bg, sidebar, surface, surface2, border, borderStrong;
  QColor text, muted, faint;
  QColor accent, accentText, accentSoft;
  QColor success, warning, danger, info;
  QColor feltInner, feltOuter, rail, railEdge;
  QColor cardFace, cardBack, cardBackAlt;
};

class Theme : public QObject {
  Q_OBJECT
 public:
  enum class Mode { Dark, Light };

  static Theme& instance();
  static const ThemeColors& colors() { return instance().colors_; }
  static Mode mode() { return instance().mode_; }

  // "dark" / "light" / "system" (system follows the platform colour scheme).
  void apply(const QString& name);
  Mode resolvedMode() const { return mode_; }

  // A tone colour blended onto the surface (for soft pill/badge backgrounds).
  static QColor soft(const QColor& c, qreal amount = 0.16);

 Q_SIGNALS:
  void changed();

 private:
  Theme() = default;
  QString styleSheet() const;

  Mode mode_ = Mode::Dark;
  ThemeColors colors_;
};
