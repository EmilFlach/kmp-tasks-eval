# KMP Tasks Eval Report

Generated: 2026-03-25 09:52:18

## Summary

| Agent | Tasks | Pass Rate | Avg Similarity | Build Pass | Judge ✅/⚠️/❌ | Kotlin Tool |
|-------|-------|-----------|----------------|------------|----------------|-------------|
| Junie | 1 | 0% | 0.28 | 0% | 🔴 | no |

---

## Junie

| Task | Category | Pass Rate | Avg Similarity | Build Pass | Judge |
|------|----------|-----------|----------------|------------|-------|
| Generate a full KMP project from scratch | Generating | 0% | 0.28 | 0% | 🔴 |

### Run Details

#### ❌ Generate a full KMP project from scratch — run 1

sim `28%` · build 🔴 · judge 🔴 no
> The agent's project fails to build, is missing critical files (shared module, iOS app files, web resources, test files, gradle.properties, logback.xml), uses wrong Material2 instead of Material3 dependencies, lacks the composeHotReload plugin, and is missing the shared module entirely which the reference project depends on.

**File checks:**
- ✗ .gitignore: 15% match (need 50%)
- ✗ README.md: 0% match (need 50%)
- ✓ build.gradle.kts: 78% match (need 50%)
- ✓ composeApp/build.gradle.kts: 63% match (need 50%)
- ✓ composeApp/src/androidMain/AndroidManifest.xml: 75% match (need 50%)
- ✓ composeApp/src/androidMain/kotlin/org/example/project/MainActivity.kt: 95% match (need 50%)
- ✗ composeApp/src/androidMain/res/drawable-v24/ic_launcher_foreground.xml: 0% match (need 50%)
- ✗ composeApp/src/androidMain/res/drawable/ic_launcher_background.xml: 0% match (need 50%)
- ✗ composeApp/src/androidMain/res/mipmap-anydpi-v26/ic_launcher.xml: 0% match (need 50%)
- ✗ composeApp/src/androidMain/res/mipmap-anydpi-v26/ic_launcher_round.xml: 0% match (need 50%)
- ✓ composeApp/src/androidMain/res/values/strings.xml: 86% match (need 50%)
- ✗ composeApp/src/commonMain/composeResources/drawable/compose-multiplatform.xml: 0% match (need 50%)
- ✓ composeApp/src/commonMain/kotlin/org/example/project/App.kt: 62% match (need 50%)
- ✗ composeApp/src/commonTest/kotlin/org/example/project/ComposeAppCommonTest.kt: 0% match (need 50%)
- ✓ composeApp/src/iosMain/kotlin/org/example/project/MainViewController.kt: 100% match (need 50%)
- ✗ composeApp/src/jvmMain/kotlin/org/example/project/main.kt: 0% match (need 50%)
- ✗ composeApp/src/webMain/kotlin/org/example/project/main.kt: 0% match (need 50%)
- ✗ composeApp/src/webMain/resources/index.html: 0% match (need 50%)
- ✗ composeApp/src/webMain/resources/styles.css: 0% match (need 50%)
- ✗ gradle.properties: 0% match (need 50%)
- ✗ gradle/libs.versions.toml: 23% match (need 50%)
- ✓ gradle/wrapper/gradle-wrapper.properties: 86% match (need 50%)
- ✓ gradlew: 98% match (need 50%)
- ✓ gradlew.bat: 96% match (need 50%)
- ✗ iosApp/Configuration/Config.xcconfig: 0% match (need 50%)
- ✗ iosApp/iosApp.xcodeproj/project.pbxproj: 0% match (need 50%)
- ✗ iosApp/iosApp.xcodeproj/project.xcworkspace/contents.xcworkspacedata: 0% match (need 50%)
- ✗ iosApp/iosApp/Assets.xcassets/AccentColor.colorset/Contents.json: 0% match (need 50%)
- ✗ iosApp/iosApp/Assets.xcassets/AppIcon.appiconset/Contents.json: 0% match (need 50%)
- ✗ iosApp/iosApp/Assets.xcassets/Contents.json: 0% match (need 50%)
- ✗ iosApp/iosApp/ContentView.swift: 0% match (need 50%)
- ✗ iosApp/iosApp/Info.plist: 0% match (need 50%)
- ✗ iosApp/iosApp/Preview Content/Preview Assets.xcassets/Contents.json: 0% match (need 50%)
- ✗ iosApp/iosApp/iOSApp.swift: 0% match (need 50%)
- ✗ local.properties: 0% match (need 50%)
- ✓ server/build.gradle.kts: 63% match (need 50%)
- ✓ server/src/main/kotlin/org/example/project/Application.kt: 88% match (need 50%)
- ✗ server/src/main/resources/logback.xml: 0% match (need 50%)
- ✓ server/src/test/kotlin/org/example/project/ApplicationTest.kt: 80% match (need 50%)
- ✓ settings.gradle.kts: 62% match (need 50%)
- ✗ shared/build.gradle.kts: 0% match (need 50%)
- ✗ shared/src/androidMain/kotlin/org/example/project/Platform.android.kt: 0% match (need 50%)
- ✗ shared/src/commonMain/kotlin/org/example/project/Constants.kt: 0% match (need 50%)
- ✗ shared/src/commonMain/kotlin/org/example/project/Greeting.kt: 0% match (need 50%)
- ✗ shared/src/commonMain/kotlin/org/example/project/Platform.kt: 0% match (need 50%)
- ✗ shared/src/commonTest/kotlin/org/example/project/SharedCommonTest.kt: 0% match (need 50%)
- ✗ shared/src/iosMain/kotlin/org/example/project/Platform.ios.kt: 0% match (need 50%)
- ✗ shared/src/jsMain/kotlin/org/example/project/Platform.js.kt: 0% match (need 50%)
- ✗ shared/src/jvmMain/kotlin/org/example/project/Platform.jvm.kt: 0% match (need 50%)
- ✗ shared/src/wasmJsMain/kotlin/org/example/project/Platform.wasmJs.kt: 0% match (need 50%)

<details><summary>Build output (failed)</summary>

```
WARNING: A restricted method in java.lang.System has been called
WARNING: java.lang.System::load has been called by net.rubygrapefruit.platform.internal.NativeLibraryLoader in an unnamed module (file:/Users/emil/.gradle/wrapper/dists/gradle-8.13-bin/5xuhj0ry160q40clulazy9h7d/gradle-8.13/lib/native-platform-0.22-milestone-28.jar)
WARNING: Use --enable-native-access=ALL-UNNAMED to avoid a warning for callers in this module
WARNING: Restricted methods will be blocked in a future release unless native access is enabled


FAILURE: Build failed with an exception.

* What went wrong:
Cannot locate matching tasks for an empty path. The path should include a task name (for example ':help' or 'help').

* Try:
> Run gradlew tasks to get a list of available tasks.
> For more on name expansion, please refer to https://docs.gradle.org/8.13/userguide/command_line_interface.html#sec:name_abbreviation in the Gradle documentation.
> Run with --stacktrace option to get the stack trace.
> Run with --info or --debug option to get more log output.
> Run with --scan to get full insights.
> Get more help at https://help.gradle.org.

BUILD FAILED in 4s

```

</details>

<details><summary>Agent output</summary>

```
Authenticated successfully
● gradle -v
│ WARNING: A restricted method in java.lang.System has been called
│ ...
│ Daemon JVM:    /opt/homebrew/Cellar/openjdk/25.0.2/libexec/openjdk.jdk/Contents/Home (no JDK specified, using current Java home)
│ OS:            Mac OS X 26.3.1 aarch64
Gradle version 8.13 is installed and running on Mac OS X with warnings about restricted Java methods and native access.
● Thinking
Starting project creation from scratch.
Gradle 8.13 is available.
I will follow the structure for a Kotlin Multiplatform project with `composeApp` and `server` modules.
● mkdir -p gradle/wrapper
The directory structure was successfully created without errors.
● Edited files
Created gradle/libs.versions.toml
A configuration file specifying versions and dependencies for various libraries and plugins was created successfully.
● Edited files
Created settings.gradle.kts
The settings.gradle.kts file was created with project name, feature preview enabled, plugin management, dependency repositories, and module includes configured.
● Edited files
Created build.gradle.kts
A build configuration file was created with plugin aliases set to not apply by default in subprojects.
● Edited files
Created .gitignore
A .gitignore file was created with entries to exclude various build, configuration, and system files and directories.
● mkdir -p composeApp/src/commonMain/kotlin/org/example/project
mkdir -p composeApp/src/androidMain/kotlin/org/example/project
mkdir -p composeApp/src/iosMain/kotlin/org/example/project
mkdir -p composeApp/src/desktopMain/kotlin/org/example/project
mkdir -p composeApp/src/wasmJsMain/kotlin/org/example/project
mkdir -p composeApp/src/wasmJsMain/resources
mkdir -p composeApp/src/commonTest/kotlin/org/example/project
The necessary project directories for multiple platforms and testing have been successfully created without errors.
● Edited files
Created composeApp/build.gradle.kts
A new build configuration file for a multiplatform Compose application was…
```

</details>