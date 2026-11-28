#include "theme.h"

#include <QApplication>
#include <QFont>
#include <QGuiApplication>
#include <QPalette>
#include <QStyleHints>
#include <QWidget>

namespace {

ThemeColors dark() {
  ThemeColors c;
  c.bg = QColor(0x0d, 0x0f, 0x13);
  c.sidebar = QColor(0x11, 0x14, 0x19);
  c.surface = QColor(0x16, 0x1a, 0x21);
  c.surface2 = QColor(0x1e, 0x23, 0x2c);
  c.border = QColor(0x25, 0x2b, 0x35);
  c.borderStrong = QColor(0x34, 0x3c, 0x49);
  c.text = QColor(0xe7, 0xea, 0xf0);
  c.muted = QColor(0x8b, 0x94, 0xa5);
  c.faint = QColor(0x5a, 0x63, 0x73);
  c.accent = QColor(0x6e, 0x8b, 0xff);
  c.accentText = QColor(0xff, 0xff, 0xff);
  c.success = QColor(0x3c, 0xcf, 0x91);
  c.warning = QColor(0xf3, 0xb5, 0x4a);
  c.danger = QColor(0xff, 0x5f, 0x6d);
  c.info = QColor(0x4c, 0xc3, 0xe8);
  c.feltInner = QColor(0x1c, 0x6b, 0x4c);
  c.feltOuter = QColor(0x0d, 0x3a, 0x29);
  c.rail = QColor(0x0a, 0x0c, 0x10);
  c.railEdge = QColor(0x2e, 0x35, 0x40);
  c.cardFace = QColor(0xfb, 0xfb, 0xfc);
  c.cardBack = QColor(0x3b, 0x4f, 0xc4);
  c.cardBackAlt = QColor(0x5a, 0x70, 0xe6);
  c.accentSoft = Theme::soft(c.accent, 0.20);
  return c;
}

ThemeColors light() {
  ThemeColors c;
  c.bg = QColor(0xf3, 0xf5, 0xf8);
  c.sidebar = QColor(0xfa, 0xfb, 0xfc);
  c.surface = QColor(0xff, 0xff, 0xff);
  c.surface2 = QColor(0xf2, 0xf4, 0xf7);
  c.border = QColor(0xe2, 0xe6, 0xec);
  c.borderStrong = QColor(0xcc, 0xd2, 0xdc);
  c.text = QColor(0x14, 0x18, 0x20);
  c.muted = QColor(0x5f, 0x69, 0x7a);
  c.faint = QColor(0x9a, 0xa3, 0xb2);
  c.accent = QColor(0x3f, 0x5f, 0xe8);
  c.accentText = QColor(0xff, 0xff, 0xff);
  c.success = QColor(0x12, 0x9e, 0x63);
  c.warning = QColor(0xc2, 0x7c, 0x0e);
  c.danger = QColor(0xd9, 0x36, 0x4a);
  c.info = QColor(0x10, 0x8d, 0xb8);
  c.feltInner = QColor(0x23, 0x7f, 0x5a);
  c.feltOuter = QColor(0x13, 0x4f, 0x38);
  c.rail = QColor(0x1d, 0x22, 0x2b);
  c.railEdge = QColor(0x3a, 0x42, 0x50);
  c.cardFace = QColor(0xff, 0xff, 0xff);
  c.cardBack = QColor(0x3b, 0x4f, 0xc4);
  c.cardBackAlt = QColor(0x5a, 0x70, 0xe6);
  c.accentSoft = QColor(0xe6, 0xeb, 0xfd);
  return c;
}

QString hex(const QColor& c) { return c.name(QColor::HexRgb); }

}  // namespace

Theme& Theme::instance() {
  static Theme t;
  return t;
}

QColor Theme::soft(const QColor& c, qreal amount) {
  const QColor base = instance().mode_ == Mode::Dark ? QColor(0x16, 0x1a, 0x21) : QColor(Qt::white);
  return QColor::fromRgbF(base.redF() + (c.redF() - base.redF()) * amount,
                          base.greenF() + (c.greenF() - base.greenF()) * amount,
                          base.blueF() + (c.blueF() - base.blueF()) * amount);
}

void Theme::apply(const QString& name) {
  Mode m = Mode::Dark;
  if (name == QLatin1String("light")) {
    m = Mode::Light;
  } else if (name == QLatin1String("system")) {
#if QT_VERSION >= QT_VERSION_CHECK(6, 5, 0)
    m = QGuiApplication::styleHints()->colorScheme() == Qt::ColorScheme::Light ? Mode::Light
                                                                               : Mode::Dark;
#else
    // Qt < 6.5 (e.g. Ubuntu 24.04's 6.4) has no colorScheme(): infer it from
    // the platform's default window colour.
    m = QGuiApplication::palette().color(QPalette::Window).lightness() > 128 ? Mode::Light : Mode::Dark;
#endif
  }
  mode_ = m;
  colors_ = m == Mode::Dark ? dark() : light();
  if (m == Mode::Light) colors_.accentSoft = soft(colors_.accent, 0.12);

  QPalette pal;
  pal.setColor(QPalette::Window, colors_.bg);
  pal.setColor(QPalette::WindowText, colors_.text);
  pal.setColor(QPalette::Base, colors_.surface2);
  pal.setColor(QPalette::AlternateBase, colors_.surface);
  pal.setColor(QPalette::Text, colors_.text);
  pal.setColor(QPalette::Button, colors_.surface2);
  pal.setColor(QPalette::ButtonText, colors_.text);
  pal.setColor(QPalette::Highlight, colors_.accent);
  pal.setColor(QPalette::HighlightedText, colors_.accentText);
  pal.setColor(QPalette::PlaceholderText, colors_.faint);
  pal.setColor(QPalette::ToolTipBase, colors_.surface2);
  pal.setColor(QPalette::ToolTipText, colors_.text);
  pal.setColor(QPalette::Link, colors_.accent);
  QApplication::setPalette(pal);
  qApp->setStyleSheet(styleSheet());
  Q_EMIT changed();
  for (QWidget* w : QApplication::allWidgets()) w->update();
}

QString Theme::styleSheet() const {
  const ThemeColors& c = colors_;
  QString s = QStringLiteral(R"QSS(
* { outline: none; }
QWidget { color: @text; font-size: 13px; }
QMainWindow, QWidget#Root, QStackedWidget#MainStack, QScrollArea, QWidget#PageBody { background: @bg; }
QStackedWidget { background: transparent; }
QWidget#Sidebar { background: @sidebar; border-right: 1px solid @border; }
QWidget#TopBar { background: @bg; border-bottom: 1px solid @border; }
QLabel { background: transparent; }
QLabel#Brand { font-size: 19px; font-weight: 700; letter-spacing: 0.5px; color: @text; }
QLabel#BrandSub { color: @muted; font-size: 11px; letter-spacing: 1.5px; }
QLabel[role="title"] { font-size: 21px; font-weight: 600; }
QLabel[role="subtitle"] { color: @muted; font-size: 13px; }
QLabel[role="section"] { color: @muted; font-size: 11px; font-weight: 600; letter-spacing: 1.2px; }
QLabel[role="metric"] { font-size: 22px; font-weight: 600; }
QLabel[role="metricSmall"] { font-size: 15px; font-weight: 600; }
QLabel[role="muted"] { color: @muted; }
QLabel[role="faint"] { color: @faint; font-size: 12px; }
QLabel[role="mono"] { font-family: "JetBrains Mono", "DejaVu Sans Mono", "Noto Sans Mono", monospace; font-size: 12px; color: @muted; }
QLabel[role="banner"] { background: @dangerSoft; color: @danger; border: 1px solid @dangerLine; border-radius: 8px; padding: 8px 12px; }
QLabel[role="note"] { background: @warningSoft; color: @warning; border: 1px solid @warningLine; border-radius: 8px; padding: 8px 12px; }

QFrame[card="true"] { background: @surface; border: 1px solid @border; border-radius: 14px; }
QFrame[divider="true"] { background: @border; max-height: 1px; min-height: 1px; border: none; }

QPushButton#NavButton {
  background: transparent; color: @muted; border: none; border-radius: 9px;
  padding: 9px 12px; text-align: left; font-size: 13px; font-weight: 500;
}
QPushButton#NavButton:hover { background: @surface2; color: @text; }
QPushButton#NavButton:checked { background: @accentSoft; color: @text; font-weight: 600; }

QPushButton {
  background: @surface2; color: @text; border: 1px solid @border; border-radius: 9px;
  padding: 7px 14px; font-weight: 500;
}
QPushButton:hover { border-color: @borderStrong; background: @hover; }
QPushButton:pressed { background: @border; }
QPushButton:disabled { color: @faint; background: @surface; border-color: @border; }
QPushButton[kind="primary"] { background: @accent; color: @accentText; border: 1px solid @accent; font-weight: 600; }
QPushButton[kind="primary"]:hover { background: @accentHover; border-color: @accentHover; }
QPushButton[kind="primary"]:disabled { background: @accentSoft; border-color: @accentSoft; color: @faint; }
QPushButton[kind="danger"] { background: @dangerSoft; color: @danger; border: 1px solid @dangerLine; font-weight: 600; }
QPushButton[kind="danger"]:hover { background: @danger; color: #ffffff; }
QPushButton[kind="ghost"] { background: transparent; border: 1px solid transparent; color: @muted; }
QPushButton[kind="ghost"]:hover { background: @surface2; color: @text; }
QPushButton[kind="chip"] { background: @surface2; border-radius: 15px; padding: 6px 14px; }
QPushButton[kind="chip"]:hover { background: @accentSoft; border-color: @accent; }
QPushButton:checked[kind="toggle"] { background: @accentSoft; border-color: @accent; color: @text; }

QLineEdit, QSpinBox, QComboBox, QPlainTextEdit, QTextEdit {
  background: @surface2; border: 1px solid @border; border-radius: 9px; padding: 6px 10px;
  selection-background-color: @accent; selection-color: @accentText;
}
QPlainTextEdit, QTextEdit { padding: 8px; font-family: "JetBrains Mono", "DejaVu Sans Mono", "Noto Sans Mono", monospace; font-size: 12px; }
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus, QTextEdit:focus { border-color: @accent; }
QLineEdit#UrlEdit { font-family: "JetBrains Mono", "DejaVu Sans Mono", monospace; font-size: 12px; min-width: 260px; }
QSpinBox::up-button, QSpinBox::down-button { width: 0px; border: none; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox::down-arrow { image: url(:/icons/chevron-@mode.svg); width: 12px; height: 12px; margin-right: 8px; }
QComboBox QAbstractItemView { background: @surface; border: 1px solid @border; border-radius: 8px; padding: 4px; selection-background-color: @accentSoft; selection-color: @text; }

QCheckBox { spacing: 8px; background: transparent; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 5px; border: 1px solid @borderStrong; background: @surface2; }
QCheckBox::indicator:hover { border-color: @accent; }
QCheckBox::indicator:checked { background: @accent; border-color: @accent; image: url(:/icons/check.svg); }
QRadioButton { spacing: 8px; background: transparent; }
QRadioButton::indicator { width: 14px; height: 14px; border-radius: 8px; border: 1px solid @borderStrong; background: @surface2; }
QRadioButton::indicator:checked { background: @accent; border: 4px solid @surface2; }

QTreeWidget, QListWidget, QTableWidget {
  background: @surface; alternate-background-color: @surface; border: none; border-radius: 10px;
}
QTreeWidget::item, QListWidget::item { padding: 5px 4px; border: none; }
QTreeWidget::item:hover, QListWidget::item:hover { background: @surface2; }
QTreeWidget::item:selected, QListWidget::item:selected { background: @accentSoft; color: @text; }
QTreeWidget[mono="true"] { font-family: "JetBrains Mono", "DejaVu Sans Mono", "Noto Sans Mono", monospace; font-size: 12px; }
QHeaderView { background: transparent; }
QHeaderView::section { background: @surface; color: @muted; border: none; border-bottom: 1px solid @border; padding: 6px 6px; font-size: 11px; font-weight: 600; }

QTabWidget::pane { border: none; }
QTabBar { qproperty-drawBase: 0; }
QTabWidget::tab-bar { left: 0px; }
QTabBar::tab { background: transparent; color: @muted; padding: 6px 14px; margin-right: 4px; border-radius: 8px; }
QTabBar::tab:hover { color: @text; background: @surface2; }
QTabBar::tab:selected { color: @text; background: @accentSoft; font-weight: 600; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: @border; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: @borderStrong; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: @border; border-radius: 4px; min-width: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QSplitter::handle { background: transparent; }
QToolTip { background: @surface2; color: @text; border: 1px solid @border; border-radius: 6px; padding: 5px 8px; }
QStatusBar { background: @sidebar; color: @muted; border-top: 1px solid @border; font-size: 12px; }
QStatusBar::item { border: none; }
QMessageBox { background: @surface; }
QMessageBox QLabel { color: @text; }
QDialog { background: @surface; }
QMenu { background: @surface; border: 1px solid @border; border-radius: 8px; padding: 4px; }
QMenu::item { padding: 6px 18px; border-radius: 6px; }
QMenu::item:selected { background: @accentSoft; }
)QSS");
  const bool darkMode = mode_ == Mode::Dark;
  const QColor hover = darkMode ? c.surface2.lighter(115) : c.surface2.darker(103);
  const QColor accentHover = darkMode ? c.accent.lighter(112) : c.accent.darker(110);
  const qreal softAmt = darkMode ? 0.16 : 0.10;
  const qreal lineAmt = darkMode ? 0.38 : 0.30;
  // Longest names first so "@accentText" is not clobbered by "@accent".
  const std::pair<const char*, QColor> vars[] = {
      {"@accentHover", accentHover},
      {"@accentSoft", c.accentSoft},
      {"@accentText", c.accentText},
      {"@accent", c.accent},
      {"@dangerSoft", soft(c.danger, softAmt)},
      {"@dangerLine", soft(c.danger, lineAmt)},
      {"@danger", c.danger},
      {"@warningSoft", soft(c.warning, softAmt)},
      {"@warningLine", soft(c.warning, lineAmt)},
      {"@warning", c.warning},
      {"@borderStrong", c.borderStrong},
      {"@border", c.border},
      {"@surface2", c.surface2},
      {"@surface", c.surface},
      {"@sidebar", c.sidebar},
      {"@hover", hover},
      {"@muted", c.muted},
      {"@faint", c.faint},
      {"@text", c.text},
      {"@bg", c.bg},
  };
  for (const auto& [k, v] : vars) s.replace(QLatin1String(k), hex(v));
  s.replace(QLatin1String("@mode"), darkMode ? QStringLiteral("dark") : QStringLiteral("light"));
  return s;
}
