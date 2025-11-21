#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Demo Service 启动脚本（Python版本）
同时启动后端（FastAPI）和前端（Vite）
"""
import os
import sys
import subprocess
import signal
import time
import threading
from pathlib import Path

# 颜色输出
GREEN = '\033[0;32m'
BLUE = '\033[0;34m'
YELLOW = '\033[1;33m'
NC = '\033[0m'  # No Color


def print_colored(text, color=NC):
    """打印彩色文本"""
    print(f"{color}{text}{NC}")


def check_command(cmd, name):
    """检查命令是否存在"""
    try:
        subprocess.run([cmd, '--version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print_colored(f"错误: 未找到 {name}", YELLOW)
        return False


def find_venv_python(project_root):
    """查找虚拟环境中的 Python 解释器"""
    venv_paths = [
        project_root / '.venv' / 'bin' / 'python',
        project_root / '.venv' / 'bin' / 'python3',
        project_root / 'venv' / 'bin' / 'python',
        project_root / 'venv' / 'bin' / 'python3',
        project_root / 'env' / 'bin' / 'python',
        project_root / 'env' / 'bin' / 'python3',
    ]
    
    for venv_python in venv_paths:
        if venv_python.exists() and venv_python.is_file():
            return str(venv_python)
    
    # 检查当前是否在虚拟环境中
    if os.environ.get('VIRTUAL_ENV'):
        venv_python = Path(os.environ['VIRTUAL_ENV']) / 'bin' / 'python'
        if venv_python.exists():
            return str(venv_python)
    
    return None


def check_python_module(python_exec, module_name):
    """检查 Python 模块是否已安装"""
    try:
        result = subprocess.run(
            [python_exec, '-c', f'import {module_name}'],
            capture_output=True,
            check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def stream_output(process, prefix):
    """实时输出进程的输出"""
    try:
        for line in iter(process.stdout.readline, ''):
            if line:
                print(f"[{prefix}] {line.rstrip()}")
    except Exception:
        pass


def main():
    """主函数"""
    print_colored("========================================", BLUE)
    print_colored("  AI Demo Service 启动脚本", BLUE)
    print_colored("========================================", BLUE)

    # 检查环境
    if not check_command('python3', 'python3'):
        sys.exit(1)
    if not check_command('node', 'node'):
        sys.exit(1)

    # 获取项目根目录
    project_root = Path(__file__).parent.parent
    backend_dir = project_root / 'backend'
    os.chdir(backend_dir)
    
    # 查找虚拟环境
    venv_python = find_venv_python(project_root)
    python_exec = venv_python if venv_python else sys.executable
    
    if venv_python:
        print_colored(f"检测到虚拟环境: {venv_python}", GREEN)
    else:
        print_colored("未检测到虚拟环境，使用系统 Python", YELLOW)
        print_colored("提示: 建议创建虚拟环境: python3 -m venv .venv", YELLOW)
    
    # 检查必要的 Python 模块
    print_colored("检查依赖...", BLUE)
    if not check_python_module(python_exec, 'uvicorn'):
        print_colored("错误: 未找到 uvicorn 模块", YELLOW)
        print_colored("\n请先安装依赖:", YELLOW)
        if venv_python:
            print_colored(f"  {venv_python} -m pip install -e .", GREEN)
        else:
            print_colored("  python3 -m venv .venv", GREEN)
            print_colored("  source .venv/bin/activate  # Windows: .venv\\Scripts\\activate", GREEN)
            print_colored("  pip install -e .", GREEN)
        sys.exit(1)
    
    if not check_python_module(python_exec, 'app'):
        print_colored("警告: 未找到 app 模块，尝试安装...", YELLOW)
        try:
            subprocess.run(
                [python_exec, '-m', 'pip', 'install', '-e', str(backend_dir)],
                check=True,
                capture_output=True
            )
            print_colored("依赖安装成功", GREEN)
        except subprocess.CalledProcessError:
            print_colored(f"依赖安装失败，请手动运行: cd {backend_dir} && pip install -e .", YELLOW)
            sys.exit(1)

    processes = []
    threads = []

    try:
        # 启动后端服务
        print_colored("启动后端服务 (FastAPI)...", GREEN)
        backend_cmd = [
            python_exec, '-m', 'uvicorn',
            'app.main:app',
            '--reload',
            '--port', '8113'
        ]
        backend_process = subprocess.Popen(
            backend_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        processes.append(backend_process)
        
        # 启动输出流线程
        backend_thread = threading.Thread(
            target=stream_output,
            args=(backend_process, "后端"),
            daemon=True
        )
        backend_thread.start()
        threads.append(backend_thread)

        # 等待后端启动
        time.sleep(2)
        
        # 检查后端是否还在运行
        if backend_process.poll() is not None:
            print_colored("错误: 后端服务启动失败", YELLOW)
            sys.exit(1)

        # 启动前端服务
        print_colored("启动前端服务 (Vite)...", GREEN)
        frontend_dir = project_root / 'frontend'
        frontend_cmd = ['npm', 'run', 'dev']
        frontend_process = subprocess.Popen(
            frontend_cmd,
            cwd=frontend_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        processes.append(frontend_process)
        
        # 启动输出流线程
        frontend_thread = threading.Thread(
            target=stream_output,
            args=(frontend_process, "前端"),
            daemon=True
        )
        frontend_thread.start()
        threads.append(frontend_thread)

        # 等待前端启动
        time.sleep(2)
        
        # 检查前端是否还在运行
        if frontend_process.poll() is not None:
            print_colored("错误: 前端服务启动失败", YELLOW)
            backend_process.terminate()
            sys.exit(1)

        print_colored("========================================", BLUE)
        print_colored("服务已启动！", GREEN)
        print_colored("========================================", BLUE)
        print_colored("后端服务: http://localhost:8113", GREEN)
        print_colored("前端服务: http://localhost:3000", GREEN)
        print_colored("API文档: http://localhost:8113/docs", GREEN)
        print_colored("========================================", BLUE)
        print_colored("按 Ctrl+C 停止所有服务", YELLOW)
        print_colored("========================================", BLUE)

        # 等待进程（使用轮询方式，避免阻塞）
        try:
            while True:
                # 检查是否有进程退出
                for process in processes:
                    if process.poll() is not None:
                        print_colored(f"\n警告: 进程意外退出 (退出码: {process.returncode})", YELLOW)
                        raise KeyboardInterrupt
                time.sleep(1)
        except KeyboardInterrupt:
            print_colored("\n正在停止服务...", YELLOW)
            for process in processes:
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                except Exception:
                    pass

    except Exception as e:
        print_colored(f"启动失败: {e}", YELLOW)
        for process in processes:
            process.terminate()
        sys.exit(1)


if __name__ == '__main__':
    main()

