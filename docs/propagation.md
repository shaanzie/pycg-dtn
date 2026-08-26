# Propagation

Satellites have no ephemeris of their own, so one is computed from their orbital
elements before the geometry runs. This happens automatically — you define an
orbit on {doc}`satellites` and never call anything here.

## The model

Orbits are propagated as **two-body motion**: the satellite and its central
body, nothing else. 

The result is loaded into SPICE as an ordinary ephemeris object. 

Propagation happens when you generate, not when you add the satellite. The generated ephemerides are
temporary and are discarded once the plan is built; nothing is written to your
kernel directory.