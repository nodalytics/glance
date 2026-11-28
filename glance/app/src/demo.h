#pragma once

class MainWindow;

// Populate every page with representative sample data (no server needed):
// used by --demo and by --screenshot to check the design offline.
void loadDemo(MainWindow& w);
