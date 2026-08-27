"""Shared SolidWorks API constants (mirrored to avoid early-binding dependency)."""

# Document types (ModelDoc2.GetType)
swDocPART = 1
swDocASSEMBLY = 2
swDocDRAWING = 3

# Open/save option flags
swOpenDocOptions_Silent = 1
swSaveAsOptions_Silent = 1
swFileSaveErrorNone = 0

# Mate types (AddMate5)
swMateCOINCIDENT = 0
swMateCONCENTRIC = 1
swMateDISTANCE = 5

# Feature suppression states (SetSuppression2)
swFeatureSuppressed = 0
swFeatureUnsuppressed = 1
