import subprocess
import os
import argparse
import signal
import psutil
from datetime import datetime
from rich.console import Console
from rich.table import Table

PATH = os.path.dirname(os.path.abspath(__file__))
PID_FILE = f'{PATH}/dxforge.pid'
LOG_FILE = f'{PATH}/dxforge.log'


def start(delete_log=True, docker_socket="unix:///var/run/docker.sock", detach=False):
    if delete_log is None:
        delete_log = True

    console = Console()
    if os.path.exists(PID_FILE):
        console.print(f"[yellow]PID file {PID_FILE} already exists. Checking if the Forge is running...[/yellow]")
        with open(PID_FILE, 'r') as pid_file:
            pid = int(pid_file.read().strip())
        try:
            os.kill(pid, 0)
            console.print(f"[yellow][gold3]dxforge[/gold3] with PID {pid} is already running[/yellow]")
            return
        except ProcessLookupError:
            console.print(f"[yellow][gold3]dxforge[/gold3] with PID {pid} is not running, removing PID file...[/yellow]")
            os.remove(PID_FILE)

    console.print("[cyan]Starting [gold3]dxforge[/gold3]...[/cyan]")

    if delete_log:
        try:
            os.remove(LOG_FILE)
        except FileNotFoundError:
            pass
        console.print("[cyan]Log file deleted[/cyan]")

    if detach:
        with open(LOG_FILE, 'a') as log_file:
            # use absolute path to python to avoid issues with virtual environments
            python_path = subprocess.check_output(['which', 'python']).decode().strip()

            process = subprocess.Popen(
                [f"nohup", python_path, "-m", "dxforge.app", "--docker-socket", docker_socket],
                stdout=log_file,
                stderr=log_file,
                preexec_fn=os.setpgrp
            )
            with open(PID_FILE, 'w') as pid_file:
                pid_file.write(str(process.pid))
        console.print(f"[gold3]dxforge[/gold3] [green]started with PID {process.pid}[/green]")
    else:
        # run the script in the foreground
        python_path = subprocess.check_output(['which', 'python']).decode().strip()
        process = subprocess.Popen([python_path, "-m", "dxforge.app", "--docker-socket", docker_socket])
        with open(PID_FILE, 'w') as pid_file:
            pid_file.write(str(process.pid))
        console.print(f"[gold3]dxforge[/gold3] [green]started with PID {process.pid}[/green]")

        try:
            process.wait()
        except KeyboardInterrupt:
            process.terminate()
            console.print("[yellow]Stopped...[/yellow]")
        finally:
            os.remove(PID_FILE)


def stop(delete_log=False):
    console = Console()
    try:
        with open(PID_FILE, 'r') as pid_file:
            pid = int(pid_file.read().strip())
        os.killpg(os.getpgid(pid), signal.SIGTERM)
        os.remove(PID_FILE)
        console.print(f"[red][gold3]dxforge[/gold3] with PID {pid} stopped[/red]")
        if delete_log:
            try:
                os.remove(LOG_FILE)
            except FileNotFoundError:
                pass
            console.print("[cyan]Log file deleted[/cyan]")
    except FileNotFoundError:
        console.print("[yellow]PID file not found. Is [gold3]dxforge[/gold3] running?[/yellow]")
    except ProcessLookupError:
        console.print("[yellow]No such process. [gold3]dxforge[/gold3] may not be running.[/yellow]")
    except Exception as e:
        console.print(f"[red]Error stopping [gold3]dxforge[/gold3]: {e}[/red]")


def status():
    """Prints to console the status of the script, similar to that of systemctl status command"""
    console = Console()
    table = Table(title="[gold3]dxforge[/gold3] is [green]active[/green] (running)")
    table.add_column("Property")
    table.add_column("Value")

    if os.path.exists(PID_FILE):
        with open(PID_FILE, 'r') as pid_file:
            pid = int(pid_file.read().strip())
        try:
            p = psutil.Process(pid)
            uptime = datetime.now() - datetime.fromtimestamp(p.create_time())
            table.add_row("Service Name", "[gold3]dxforge[/gold3]")
            table.add_row("Loaded", f"loaded (dxforge.app.main)")
            table.add_row("Active", f"active (running) since "
                                    f"{datetime.fromtimestamp(p.create_time()).strftime('%Y-%m-%d %H:%M:%S')}; ")
            table.add_row("Uptime", f"{uptime.days}d "
                                    f"{uptime.seconds // 3600}h "
                                    f"{(uptime.seconds // 60) % 60:02d}m "
                                    f"{uptime.seconds % 60:02d}s")
            table.add_row("Main PID", f"[green]{pid} (python)[/green]")
            table.add_row("Tasks", f"{p.num_threads()}")
            table.add_row("Memory", f"{p.memory_info().rss / (1024 * 1024):.1f}M")
            table.add_row("CPU", f"{p.cpu_times().user:.1f}s")

            console.print(table)

            console.print("\nLast 10 lines of the log file:")
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, 'r') as log_file:
                    lines = log_file.readlines()
                    last_lines = lines[-10:] if len(lines) > 10 else lines
                    for line in last_lines:
                        console.print(line, end='')
            else:
                console.print("[yellow]Log file not found.[/yellow]")
        except psutil.NoSuchProcess:
            console.print(f"[yellow]PID {pid} is not running, but PID file exists.[/yellow]")
    else:
        console.print("[yellow]dxforge is not running[/yellow]")


def restart():
    """Restarts the script"""
    stop()
    start()


def logs():
    """Prints the contents of the log file to the console"""
    console = Console()
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as log_file:
            for line in log_file:
                console.print(line, end='')
    else:
        console.print("[yellow]Log file not found.[/yellow]")


def systemd():
    """Creates a config folder to allow user to use the systemd service"""
    raise NotImplementedError


def main():
    parser = argparse.ArgumentParser(description="Start or stop the dxforge instance.")
    parser.add_argument('command', choices=['start', 'stop', 'status', 'logs', 'systemd', 'restart'],
                        help='Start, stop, check status, show logs, or configure systemd for the script.')

    # add option to delete the log file (if start, delete previous, if stop, delete current)
    parser.add_argument('--delete-log', action='store_true', help='Delete the log file.', default=None)
    parser.add_argument('--docker-socket', help='Docker socket to use.')

    # if user adds -d tag, set detach to True
    parser.add_argument('-d', '--detach', action='store_true', help='Run the script in the background.')

    args = parser.parse_args()

    if args.command == 'start':
        start(args.delete_log, args.docker_socket, args.detach)
    elif args.command == 'stop':
        stop(args.delete_log)
    elif args.command == 'status':
        status()
    elif args.command == 'restart':
        restart()
    elif args.command == 'logs':
        logs()
    elif args.command == 'systemd':
        systemd()
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
