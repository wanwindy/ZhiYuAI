lib/features/favorites/presentation/favorites_page.dart:116:3: Error: Type 'TranslationResponseDto' not found.
  TranslationResponseDto _toDto(FavoriteItem it) => TranslationResponseDto(
  ^^^^^^^^^^^^^^^^^^^^^^
../../../../AppData/Local/Pub/Cache/hosted/pub.dev/record_linux-0.7.2/lib/record_linux.dart:12:7: Error: The non-abstract class 'RecordLinux' is missing implementations for these members:
 - RecordMethodChannelPlatformInterface.startStream
Try to either
 - provide an implementation,
 - inherit an implementation from a superclass or mixin,
 - mark the class as abstract, or
 - provide a 'noSuchMethod' implementation.

class RecordLinux extends RecordPlatform {
      ^^^^^^^^^^^
../../../../AppData/Local/Pub/Cache/hosted/pub.dev/record_platform_interface-1.4.0/lib/src/record_platform_interface.dart:46:29: Context: 'RecordMethodChannelPlatformInterface.startStream' is defined here.
  Future<Stream<Uint8List>> startStream(String recorderId, RecordConfig config);
                            ^^^^^^^^^^^
lib/features/translate/presentation/translate_page.dart:167:33: Error: The getter 'translationRepositoryProvider' isn't defined for the type '_AssessButton'.
 - '_AssessButton' is from 'package:gummy_translator_mobile/features/translate/presentation/translate_page.dart' ('lib/features/translate/presentation/translate_page.dart').
Try correcting the name to the name of an existing getter, or defining a getter or field named 'translationRepositoryProvider'.
          final repo = ref.read(translationRepositoryProvider);
                                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
lib/features/translate/presentation/translate_page.dart:344:27: Error: The getter 'favoritesRepositoryProvider' isn't defined for the type '_FavoriteButtonState'.
 - '_FavoriteButtonState' is from 'package:gummy_translator_mobile/features/translate/presentation/translate_page.dart' ('lib/features/translate/presentation/translate_page.dart').
Try correcting the name to the name of an existing getter, or defining a getter or field named 'favoritesRepositoryProvider'.
    final repo = ref.read(favoritesRepositoryProvider);
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^
lib/features/translate/presentation/translate_page.dart:345:16: Error: The getter 'FavoritesRepository' isn't defined for the type '_FavoriteButtonState'.
 - '_FavoriteButtonState' is from 'package:gummy_translator_mobile/features/translate/presentation/translate_page.dart' ('lib/features/translate/presentation/translate_page.dart').
Try correcting the name to the name of an existing getter, or defining a getter or field named 'FavoritesRepository'.
    final id = FavoritesRepository.buildId(widget.res);
               ^^^^^^^^^^^^^^^^^^^
lib/features/translate/presentation/translate_page.dart:360:31: Error: The getter 'favoritesRepositoryProvider' isn't defined for the type '_FavoriteButtonState'.
 - '_FavoriteButtonState' is from 'package:gummy_translator_mobile/features/translate/presentation/translate_page.dart' ('lib/features/translate/presentation/translate_page.dart').
Try correcting the name to the name of an existing getter, or defining a getter or field named 'favoritesRepositoryProvider'.
        final repo = ref.read(favoritesRepositoryProvider);
                              ^^^^^^^^^^^^^^^^^^^^^^^^^^^
lib/features/translate/presentation/translate_page.dart:361:20: Error: The getter 'FavoritesRepository' isn't defined for the type '_FavoriteButtonState'.
 - '_FavoriteButtonState' is from 'package:gummy_translator_mobile/features/translate/presentation/translate_page.dart' ('lib/features/translate/presentation/translate_page.dart').
Try correcting the name to the name of an existing getter, or defining a getter or field named 'FavoritesRepository'.
        final id = FavoritesRepository.buildId(widget.res);
                   ^^^^^^^^^^^^^^^^^^^
lib/features/favorites/presentation/favorites_page.dart:116:53: Error: The method 'TranslationResponseDto' isn't defined for the type 'FavoritesPage'.
 - 'FavoritesPage' is from 'package:gummy_translator_mobile/features/favorites/presentation/favorites_page.dart' ('lib/features/favorites/presentation/favorites_page.dart').
Try correcting the name to the name of an existing method, or defining a method named 'TranslationResponseDto'.
  TranslationResponseDto _toDto(FavoriteItem it) => TranslationResponseDto(
                                                    ^^^^^^^^^^^^^^^^^^^^^^
lib/shared/export_utils.dart:61:35: Error: Undefined name 'safe_'.
  final file = File('${dir.path}/$safe_$ts.$ext');
                                  ^^^^^
lib/features/voice/providers.dart:51:26: Error: Required named parameter 'path' must be provided.
    await _recorder.start(
                         ^
Target kernel_snapshot_program failed: Exception


FAILURE: Build failed with an exception.

* What went wrong:
Execution failed for task ':app:compileFlutterBuildDebug'.
> Process 'command 'D:\flutter\bin\flutter.bat'' finished with non-zero exit value 1

* Try:
> Run with --stacktrace option to get the stack trace.
> Run with --info or --debug option to get more log output.
> Run with --scan to get full insights.
> Get more help at https://help.gradle.org.

BUILD FAILED in 10m 18s
Running Gradle task 'assembleDebug'...                            619.0s
Error: Gradle task assembleDebug failed with exit code 1

C:\Users\ZhuanZ\Downloads\gummy-translator-main\mobile-app\flutter>