#!/usr/bin/env python3
"""
Transcripta Build System
========================
A robust, cross-platform build orchestration script.

Usage:
    python scripts/build.py [command] [options]

Commands:
    dev          - Fast incremental build with hot reload
    production   - Full optimized production build
    clean        - Clean all build artifacts
    analyze      - Analyze bundle size
    version      - Show version info

Options:
    --platform   - Target platform (win, mac, linux, all)
    --arch       - Target architecture (x64, arm64, ia32)
    --verbose    - Verbose output
    --cache      - Enable build caching
    --sign       - Enable code signing
"""

import os
import sys
import json
import shutil
import subprocess
import argparse
import hashlib
import time
import platform as sys_platform
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# Build Configuration
BUILD_DIR = Path("build")
CACHE_DIR = Path(".cache")
DIST_DIR = Path("dist")
RELEASE_DIR = Path("release")

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

class BuildError(Exception):
    """Custom build error with context"""
    pass

@dataclass
class BuildConfig:
    """Build configuration container"""
    environment: str = "development"
    platform: str = "current"
    arch: str = "x64"
    verbose: bool = False
    cache_enabled: bool = True
    sign_enabled: bool = False
    parallel: bool = True
    source_maps: bool = True
    minify: bool = False
    tree_shake: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class BuildCache:
    """Incremental build caching system"""
    
    def __init__(self, cache_dir: Path = CACHE_DIR):
        self.cache_dir = cache_dir
        self.cache_file = cache_dir / "build_cache.json"
        self.cache_data: Dict[str, Any] = {}
        self._load()
    
    def _load(self):
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    self.cache_data = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.cache_data = {}
    
    def _save(self):
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache_data, f, indent=2)
    
    def get_file_hash(self, filepath: Path) -> str:
        """Calculate MD5 hash of file"""
        if not filepath.exists():
            return ""
        hasher = hashlib.md5()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    def is_cached(self, target: str, dependencies: List[Path]) -> bool:
        """Check if target is up to date"""
        if target not in self.cache_data:
            return False
        
        cached_deps = self.cache_data[target].get('dependencies', {})
        for dep in dependencies:
            current_hash = self.get_file_hash(dep)
            if cached_deps.get(str(dep)) != current_hash:
                return False
        return True
    
    def update_cache(self, target: str, dependencies: List[Path]):
        """Update cache for target"""
        self.cache_data[target] = {
            'timestamp': datetime.now().isoformat(),
            'dependencies': {str(d): self.get_file_hash(d) for d in dependencies}
        }
        self._save()
    
    def clear(self):
        """Clear all cached data"""
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
        self.cache_data = {}

class Logger:
    """Build logger with color support"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.start_time = time.time()
    
    def _print(self, message: str, color: str = "", bold: bool = False):
        prefix = ""
        if bold:
            prefix += Colors.BOLD
        if color:
            prefix += getattr(Colors, color.upper(), "")
        print(f"{prefix}{message}{Colors.ENDC}")
    
    def info(self, message: str):
        self._print(f"[INFO] {message}", "blue")
    
    def success(self, message: str):
        self._print(f"[SUCCESS] {message}", "green")
    
    def warning(self, message: str):
        self._print(f"[WARNING] {message}", "yellow")
    
    def error(self, message: str):
        self._print(f"[ERROR] {message}", "red", bold=True)
    
    def debug(self, message: str):
        if self.verbose:
            self._print(f"[DEBUG] {message}", "cyan")
    
    def section(self, title: str):
        print()
        self._print(f"{'='*60}", "header", bold=True)
        self._print(f"  {title}", "header", bold=True)
        self._print(f"{'='*60}", "header", bold=True)
        print()
    
    def elapsed(self) -> str:
        elapsed = time.time() - self.start_time
        return f"{elapsed:.2f}s"

class CommandRunner:
    """Cross-platform command execution"""
    
    def __init__(self, logger: Logger):
        self.logger = logger
    
    def run(self, cmd: List[str], cwd: Optional[Path] = None, 
            env: Optional[Dict[str, str]] = None, 
            check: bool = True) -> subprocess.CompletedProcess:
        """Run shell command with logging"""
        self.logger.debug(f"Running: {' '.join(cmd)}")
        if cwd:
            self.logger.debug(f"  in: {cwd}")
        
        merged_env = {**os.environ, **(env or {})}
        
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                env=merged_env,
                capture_output=not self.logger.verbose,
                text=True,
                check=check
            )
            return result
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Command failed: {' '.join(cmd)}")
            if e.stdout:
                self.logger.error(f"stdout: {e.stdout}")
            if e.stderr:
                self.logger.error(f"stderr: {e.stderr}")
            raise BuildError(f"Command failed with exit code {e.returncode}")
    
    def run_parallel(self, commands: List[tuple], max_workers: int = 4) -> List[subprocess.CompletedProcess]:
        """Run multiple commands in parallel"""
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self.run, cmd, cwd, env, False): (cmd, cwd, env)
                for cmd, cwd, env in commands
            }
            
            for future in as_completed(futures):
                cmd, cwd, env = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                    self.logger.success(f"Completed: {' '.join(cmd)}")
                except Exception as e:
                    self.logger.error(f"Failed: {' '.join(cmd)} - {e}")
                    raise BuildError(f"Parallel command failed: {e}")
        
        return results

class BuildOrchestrator:
    """Main build orchestration class"""
    
    def __init__(self, config: BuildConfig, logger: Logger):
        self.config = config
        self.logger = logger
        self.cache = BuildCache() if config.cache_enabled else None
        self.runner = CommandRunner(logger)
        
        # Detect current platform
        self.current_platform = sys_platform.system().lower()
        if self.current_platform == "darwin":
            self.current_platform = "mac"
        elif self.current_platform == "windows":
            self.current_platform = "win"
        elif self.current_platform == "linux":
            self.current_platform = "linux"
    
    def _get_npm_cmd(self) -> str:
        """Get npm command for current platform"""
        return "npm.cmd" if sys_platform.system() == "Windows" else "npm"
    
    def _get_npx_cmd(self) -> str:
        """Get npx command for current platform"""
        return "npx.cmd" if sys_platform.system() == "Windows" else "npx"
    
    def clean(self):
        """Clean build artifacts"""
        self.logger.section("CLEANING BUILD ARTIFACTS")
        
        dirs_to_clean = [
            BUILD_DIR,
            DIST_DIR,
            RELEASE_DIR,
            Path("app/electron/dist"),
            Path("app/electron/renderer/dist"),
        ]
        
        for dir_path in dirs_to_clean:
            if dir_path.exists():
                self.logger.info(f"Removing {dir_path}")
                shutil.rmtree(dir_path)
        
        if self.cache:
            self.cache.clear()
        
        self.logger.success("Clean complete")
    
    def install_dependencies(self):
        """Install all project dependencies"""
        self.logger.section("INSTALLING DEPENDENCIES")
        
        npm = self._get_npm_cmd()
        
        # Root dependencies
        self.logger.info("Installing root dependencies...")
        self.runner.run([npm, "install"])
        
        # Electron dependencies
        self.logger.info("Installing Electron dependencies...")
        self.runner.run([npm, "install"], cwd=Path("app/electron"))
        
        # Frontend dependencies
        self.logger.info("Installing frontend dependencies...")
        self.runner.run([npm, "install"], cwd=Path("app/electron/frontend"))
        
        self.logger.success("Dependencies installed")
    
    def build_frontend(self) -> bool:
        """Build frontend application"""
        self.logger.section("BUILDING FRONTEND")
        
        frontend_dir = Path("app/electron/frontend")
        
        # Check cache
        if self.cache:
            source_files = list(frontend_dir.rglob("*.{ts,tsx,js,jsx,css,scss,html}"))
            if self.cache.is_cached("frontend", source_files):
                self.logger.info("Frontend build cached, skipping...")
                return True
        
        npm = self._get_npm_cmd()
        
        # Set environment variables
        env = {
            "NODE_ENV": self.config.environment,
            "VITE_MINIFY": "true" if self.config.minify else "false",
            "VITE_SOURCEMAP": "true" if self.config.source_maps else "false",
        }
        
        self.logger.info(f"Building frontend ({self.config.environment})...")
        self.runner.run([npm, "run", "build"], cwd=frontend_dir, env=env)
        
        # Update cache
        if self.cache:
            source_files = list(frontend_dir.rglob("*.{ts,tsx,js,jsx,css,scss,html}"))
            self.cache.update_cache("frontend", source_files)
        
        self.logger.success("Frontend build complete")
        return True
    
    def build_electron(self) -> bool:
        """Build Electron main process"""
        self.logger.section("BUILDING ELECTRON MAIN")
        
        electron_dir = Path("app/electron")
        
        npm = self._get_npm_cmd()
        
        self.logger.info("Building Electron main process...")
        self.runner.run([npm, "run", "build:frontend"], cwd=electron_dir)
        
        self.logger.success("Electron main build complete")
        return True
    
    def analyze_bundle(self):
        """Analyze bundle size"""
        self.logger.section("ANALYZING BUNDLE")
        
        npm = self._get_npm_cmd()
        frontend_dir = Path("app/electron/frontend")
        
        self.logger.info("Running bundle analysis...")
        self.runner.run([npm, "run", "build"], cwd=frontend_dir, env={"ANALYZE": "true"})
        
        # Display bundle info
        dist_dir = frontend_dir / "dist"
        if dist_dir.exists():
            total_size = 0
            for file in dist_dir.rglob("*"):
                if file.is_file():
                    size = file.stat().st_size
                    total_size += size
                    if size > 1024 * 1024:  # Files larger than 1MB
                        self.logger.warning(f"Large file: {file.name} ({size / 1024 / 1024:.2f} MB)")
            
            self.logger.info(f"Total bundle size: {total_size / 1024 / 1024:.2f} MB")
        
        self.logger.success("Bundle analysis complete")
    
    def run_tests(self) -> bool:
        """Run test suite"""
        self.logger.section("RUNNING TESTS")
        
        npm = self._get_npm_cmd()
        frontend_dir = Path("app/electron/frontend")
        
        self.logger.info("Running frontend tests...")
        try:
            self.runner.run([npm, "run", "test"], cwd=frontend_dir)
            self.logger.success("All tests passed")
            return True
        except BuildError:
            self.logger.error("Tests failed")
            return False
    
    def run_lint(self) -> bool:
        """Run linting"""
        self.logger.section("RUNNING LINT")
        
        npm = self._get_npm_cmd()
        frontend_dir = Path("app/electron/frontend")
        
        try:
            self.logger.info("Running ESLint...")
            self.runner.run([npm, "run", "lint"], cwd=frontend_dir)
            self.logger.success("Linting passed")
            return True
        except BuildError:
            self.logger.warning("Linting found issues")
            return False
    
    def build_dev(self):
        """Development build with hot reload"""
        self.logger.section("DEVELOPMENT BUILD")
        
        self.config.minify = False
        self.config.source_maps = True
        self.config.environment = "development"
        
        npm = self._get_npm_cmd()
        
        # Start dev servers
        self.logger.info("Starting development servers...")
        
        # Run in foreground
        self.runner.run([npm, "run", "dev"])
    
    def build_production(self):
        """Full production build"""
        self.logger.section("PRODUCTION BUILD")
        
        self.config.minify = True
        self.config.source_maps = False
        self.config.environment = "production"
        
        start_time = time.time()
        
        try:
            # Clean first
            self.clean()
            
            # Install dependencies if needed
            if not (Path("node_modules").exists() and 
                    Path("app/electron/node_modules").exists()):
                self.install_dependencies()
            
            # Build frontend
            self.build_frontend()
            
            # Build electron
            self.build_electron()
            
            # Run tests
            if not self.run_tests():
                raise BuildError("Tests failed")
            
            # Run lint
            self.run_lint()
            
            elapsed = time.time() - start_time
            self.logger.section("BUILD COMPLETE")
            self.logger.success(f"Production build completed in {elapsed:.2f}s")
            
        except BuildError as e:
            self.logger.error(f"Build failed: {e}")
            sys.exit(1)
    
    def show_version(self):
        """Display version information"""
        package_json = Path("package.json")
        with open(package_json, 'r') as f:
            data = json.load(f)
        
        print()
        print(f"{Colors.BOLD}{Colors.HEADER}Transcripta Build System{Colors.ENDC}")
        print(f"  Version: {Colors.CYAN}{data.get('version', 'unknown')}{Colors.ENDC}")
        print(f"  Node:    {Colors.CYAN}{sys_platform.node()}{Colors.ENDC}")
        print(f"  Python:  {Colors.CYAN}{sys.version.split()[0]}{Colors.ENDC}")
        print(f"  Platform:{Colors.CYAN}{sys_platform.platform()}{Colors.ENDC}")
        print()

def main():
    parser = argparse.ArgumentParser(
        description="Transcripta Build System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/build.py dev                    # Development build with hot reload
    python scripts/build.py production             # Full production build
    python scripts/build.py production --platform win --arch x64
    python scripts/build.py clean                  # Clean build artifacts
    python scripts/build.py analyze                # Analyze bundle size
        """
    )
    
    parser.add_argument(
        "command",
        choices=["dev", "production", "prod", "clean", "analyze", "version", "test", "lint"],
        help="Build command to execute"
    )
    parser.add_argument("--platform", choices=["win", "mac", "linux", "all", "current"],
                       default="current", help="Target platform")
    parser.add_argument("--arch", choices=["x64", "arm64", "ia32", "all"],
                       default="x64", help="Target architecture")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Verbose output")
    parser.add_argument("--no-cache", action="store_true",
                       help="Disable build caching")
    parser.add_argument("--sign", action="store_true",
                       help="Enable code signing")
    parser.add_argument("--no-parallel", action="store_true",
                       help="Disable parallel builds")
    
    args = parser.parse_args()
    
    # Create config
    config = BuildConfig(
        platform=args.platform,
        arch=args.arch,
        verbose=args.verbose,
        cache_enabled=not args.no_cache,
        sign_enabled=args.sign,
        parallel=not args.no_parallel
    )
    
    # Create logger
    logger = Logger(verbose=args.verbose)
    
    # Create orchestrator
    orchestrator = BuildOrchestrator(config, logger)
    
    # Execute command
    if args.command in ["production", "prod"]:
        orchestrator.build_production()
    elif args.command == "dev":
        orchestrator.build_dev()
    elif args.command == "clean":
        orchestrator.clean()
    elif args.command == "analyze":
        orchestrator.analyze_bundle()
    elif args.command == "version":
        orchestrator.show_version()
    elif args.command == "test":
        orchestrator.run_tests()
    elif args.command == "lint":
        orchestrator.run_lint()

if __name__ == "__main__":
    main()
