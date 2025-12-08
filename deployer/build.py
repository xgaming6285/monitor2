"""
Build script to create the deployment EXE
"""
import subprocess
import sys
import shutil
from pathlib import Path


def main():
    project_root = Path(__file__).parent.parent
    deployer_dir = Path(__file__).parent
    dist_dir = deployer_dir / 'dist'
    build_dir = deployer_dir / 'build'
    
    print("=" * 50)
    print("  Building Monitor Deployer EXE")
    print("=" * 50)
    print()
    
    # Clean previous builds
    print("[1/4] Cleaning previous builds...")
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    if build_dir.exists():
        shutil.rmtree(build_dir)
    
    # Install PyInstaller if needed
    print("[2/4] Checking PyInstaller...")
    try:
        import PyInstaller
    except ImportError:
        print("      Installing PyInstaller...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyinstaller'])
    
    # Build the EXE
    print("[3/4] Building EXE...")
    
    # PyInstaller command
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',  # Single EXE
        '--windowed',  # No console (but we'll show it during setup)
        '--console',  # Actually use console for initial setup
        '--name', 'MonitorSetup',
        '--icon', 'NONE',  # No icon (use default)
        '--add-data', f'{project_root / "agent"};agent',
        '--add-data', f'{project_root / "extensions" / "chromium"};extensions/chromium',
        '--hidden-import', 'tkinter',
        '--hidden-import', 'tkinter.simpledialog',
        '--uac-admin',  # Request admin privileges
        '--clean',
        str(deployer_dir / 'deploy.py')
    ]
    
    result = subprocess.run(cmd, cwd=str(deployer_dir))
    
    if result.returncode != 0:
        print("Build failed!")
        return 1
    
    # Move the EXE to a more accessible location
    print("[4/4] Finalizing...")
    exe_path = dist_dir / 'MonitorSetup.exe'
    
    if exe_path.exists():
        final_path = project_root / 'MonitorSetup.exe'
        shutil.copy(exe_path, final_path)
        print()
        print("=" * 50)
        print("  Build Complete!")
        print("=" * 50)
        print()
        print(f"  Output: {final_path}")
        print()
        print("  Transfer this EXE to target devices and run as admin.")
        print()
    else:
        print("EXE not found after build!")
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
