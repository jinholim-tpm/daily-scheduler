"""
크로스 플랫폼 빌드 스크립트
- Mac: pyinstaller DailyScheduler.spec  (기존 .app 번들)
- Windows: pyinstaller DailyScheduler_win.spec  (단일 .exe)

Windows에서 .ico 아이콘이 없으면 PNG에서 자동 생성 시도
"""

import subprocess
import sys
import platform
import os


def ensure_ico():
    """Windows용 .ico 파일이 없으면 PNG에서 변환"""
    if os.path.exists("AppIcon.ico"):
        return True

    png = None
    for size in [256, 128, 64, 32]:
        candidate = f"icon_{size}.png"
        if os.path.exists(candidate):
            png = candidate
            break

    if not png:
        print("[WARN] PNG 아이콘 파일을 찾을 수 없습니다. 아이콘 없이 빌드합니다.")
        return False

    try:
        from PIL import Image
        img = Image.open(png)
        img.save("AppIcon.ico", format="ICO",
                 sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
        print(f"[OK] {png} → AppIcon.ico 변환 완료")
        return True
    except ImportError:
        print("[WARN] Pillow가 설치되지 않았습니다. pip install Pillow 후 다시 시도하세요.")
        print("       아이콘 없이 빌드합니다.")
        return False
    except Exception as e:
        print(f"[WARN] 아이콘 변환 실패: {e}")
        return False


def main():
    system = platform.system()

    if system == "Darwin":
        spec = "DailyScheduler.spec"
        print("[BUILD] macOS 빌드 시작...")
    elif system == "Windows":
        spec = "DailyScheduler_win.spec"
        print("[BUILD] Windows 빌드 시작...")
        ensure_ico()
    else:
        spec = "DailyScheduler_win.spec"
        print(f"[BUILD] {system} 빌드 시작 (Windows spec 사용)...")

    try:
        subprocess.check_call([sys.executable, "-m", "PyInstaller", spec])
        print("\n[OK] 빌드 완료!")
        if system == "Windows":
            print("     dist/DailyScheduler.exe 파일을 실행하세요.")
        elif system == "Darwin":
            print("     dist/DailyScheduler.app 을 실행하세요.")
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] 빌드 실패: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("\n[ERROR] PyInstaller가 설치되지 않았습니다.")
        print("        pip install pyinstaller 후 다시 시도하세요.")
        sys.exit(1)


if __name__ == "__main__":
    main()
