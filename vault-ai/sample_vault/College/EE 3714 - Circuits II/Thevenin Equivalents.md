---
tags: [ee3714, circuits]
date: 2026-09-08
---
# Thevenin Equivalents

Any linear two-terminal network can be replaced by a voltage source **V_th** in series with a resistance **R_th**.

## Finding V_th
Open-circuit the load terminals and find the voltage across them.

## Finding R_th
Turn off independent sources (voltage sources → short, current sources → open) and find the resistance looking into the terminals.
If there are dependent sources, apply a test source and use R_th = V_test / I_test.

## Worked Example
12 V source, R1 = 4 Ω in series, R2 = 12 Ω across the terminals.
V_th = 12 · 12/(4+12) = 9 V. R_th = 4 ∥ 12 = 3 Ω.

Related: [[Norton Equivalents]], [[Maximum Power Transfer]]
