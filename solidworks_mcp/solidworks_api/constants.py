"""Shared SolidWorks API constants (mirrored to avoid early-binding dependency)."""

# Document types (ModelDoc2.GetType)
swDocPART = 1
swDocASSEMBLY = 2
swDocDRAWING = 3

# Open/save option flags
swOpenDocOptions_Silent = 1
swSaveAsOptions_Silent = 1
swFileSaveErrorNone = 0

# ISO 273 medium-fit tap drill diameters (mm) and ISO 724 coarse pitches
# (mm): thread spec -> (tap drill diameter, pitch). A threaded hole is
# modeled as a plain cut cylinder at the tap-drill diameter plus a
# best-effort cosmetic thread annotation (HoleWizard needs interactive
# panels the straight-line channel cannot drive).
THREAD_SPECS = {
    "M2": (1.6, 0.4),
    "M2.5": (2.05, 0.45),
    "M3": (2.5, 0.5),
    "M4": (3.3, 0.7),
    "M5": (4.2, 0.8),
    "M6": (5.0, 1.0),
    "M8": (6.8, 1.25),
    "M10": (8.5, 1.5),
    "M12": (10.2, 1.75),
    "M16": (14.0, 2.0),
    "M20": (17.5, 2.5),
}

# Mate types (AddMate5)
swMateCOINCIDENT = 0
swMateCONCENTRIC = 1
swMateDISTANCE = 5

# Feature suppression states (SetSuppression2)
swFeatureSuppressed = 0
swFeatureUnsuppressed = 1
