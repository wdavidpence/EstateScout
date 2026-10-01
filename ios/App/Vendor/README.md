# Vendored capacitor-swift-pm 8.5.2

Proof-phase workaround, do not treat as permanent.

- Copied from the SwiftPM checkout of revision 0b6882e9a32 (v8.5.2).
- Only change: Package.swift binaryTarget(url:...) -> binaryTarget(path:...),
  pointing at Artifacts/*.xcframework.zip (downloaded from the official
  GitHub release for 8.5.2, sha256 verified against the checksums that
  Package.swift declared before the patch:
  Capacitor 134c65a8bd30bfaa8ccb158d78142fa7231bf3f472e4a5d808c5fbed90fd4c75
  Cordova   57ff2c8f1e5dcd8d4379ac3cccde1407d81ccd575347dc2aff4f72272b8794a1).
- Why: on this Mac, SwiftPM (Xcode 27 / swift-package 6.4) deadlocks on
  "Downloading" for the remote binaryTarget zips — 0% CPU, no sockets
  opened, no timeout — in both `swift build` and `xcodebuild`. curl to the
  same URLs works, so it is a SwiftPM bug, not network. Local path:
  binaryTargets resolve fine (verified with a throwaway package).
- Revert by restoring Package.swift dependency to
  .package(url: "https://github.com/ionic-team/capacitor-swift-pm.git", exact: "8.5.2")
  once a fixed SwiftPM/Xcode is installed.
