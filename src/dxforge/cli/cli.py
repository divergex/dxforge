import argparse
import multiprocessing
import os
import subprocess


def process_file(project, name, filename):
    """Process the file and display the results"""
    root_dir = project
    path = os.path.join(root_dir, filename)
    print(path)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Error: The file '{filename}' does not exist.")

    return path

def run(script):
    """Run a Python script in a separate process"""
    result = subprocess.run(["python", script], capture_output=True, text=True)

    output = result.stdout
    error = result.stderr
    return output, error

def main():
    parser = argparse.ArgumentParser(description="CLI Utility that processes a file for a given name")

    parser.add_argument('project', type=str, help="Name of the root project folder")
    parser.add_argument('name', type=str, help="Name of the user or task")
    parser.add_argument('filename', type=str, help="Path to the file to process")
    args = parser.parse_args()

    script = process_file(args.project, args.name, args.filename)
    with multiprocessing.Pool(processes=1) as pool:
        results = pool.map(run, [script])

        for result in results:
            output, error = result
            if output:
                print(f"Output:\n{output}")
            if error:
                print(f"Error:\n{error}")
