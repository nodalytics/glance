#pragma once

// Custom-painted poker table: felt, seats around an ellipse (seat 1 = the
// hero, bottom centre, clockwise), hole cards, stacks, bet chips, dealer
// button, board, pot and stage — rendered from a GET /state JSON object.

#include <QJsonObject>
#include <QSet>
#include <QStringList>
#include <QWidget>

#include <optional>

class TableView : public QWidget {
  Q_OBJECT
 public:
  explicit TableView(QWidget* parent = nullptr);
  void setState(const QJsonObject& state);
  void clearState(const QString& message, const QString& detail = {});
  QSize sizeHint() const override { return {820, 520}; }
  QSize minimumSizeHint() const override { return {520, 340}; }

 protected:
  void paintEvent(QPaintEvent*) override;

 private:
  struct Seat {
    int index = 0;
    QStringList cards;
    std::optional<double> stack, bet;
    bool inHand = false;
  };
  void paintSeat(class QPainter& p, const Seat& s, QPointF at, QPointF center, bool dealer,
                 bool hero, qreal scale);

  bool has_ = false;
  QString message_, detail_;
  int maxPlayers_ = 6;
  QList<Seat> seats_;
  int dealer_ = 0;
  std::optional<double> pot_, call_, raise_;
  QString stage_;
  QStringList board_;
  bool myTurn_ = false;
  QSet<QString> flagged_;  // slots named by validation errors
};
