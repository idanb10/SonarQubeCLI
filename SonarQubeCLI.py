import argparse
import os
import subprocess
import sys
import yaml

def load_sonarqube_url(config_path="config.yaml"):
    if not os.path.exists(config_path):
        print(f"❌ Error: Configuration file '{config_path}' not found.")
        sys.exit(1)

    try:
        with open(config_path, "r") as file:
            config = yaml.safe_load(file)
            return config["sonarqube_url"], config["sonarscanner_path"]
    except (yaml.YAMLError, KeyError) as e:
        print(f"❌ Error parsing configuration file: {e}")
        sys.exit(1)

SONARQUBE_URL, SONARSCANNER_PATH = load_sonarqube_url()

def run_command(command, cwd):
    """Helper function to execute shell commands."""
    try:
        process = subprocess.run(command, shell=True, cwd=cwd, check=True, text=True)
        print(f"✅ Successfully executed: {command}")
        return process.returncode
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed: {command}\n{e}")
        sys.exit(1)

def scan_codebase(codebase_path, language, project_key, sonarqube_token):
    """Runs SonarQube scan based on the programming language."""
    if not os.path.exists(codebase_path):
        print(f"❌ Error: Codebase path '{codebase_path}' not found.")
        sys.exit(1)

    print(f"🔍 Scanning project: {project_key} ({language}) using {SONARQUBE_URL}")

    if language.lower() in [".net framework"]:
        solution_file = None
        for file in os.listdir(codebase_path):
            if file.endswith(".sln"):
                solution_file = file
                break

        if not solution_file:
            print("❌ Error: No solution (.sln) file found in the codebase directory.")
            sys.exit(1)
            
        run_command(f'dotnet sonarscanner begin /k:"{project_key}" /d:sonar.token="{sonarqube_token}" /d:sonar.host.url="{SONARQUBE_URL}"', codebase_path)
        run_command(f'msbuild  "{solution_file}" /t:Rebuild /p:Configuration=Release', codebase_path)
        run_command(f'dotnet sonarscanner end /d:sonar.token="{sonarqube_token}"', codebase_path)

    elif language.lower() in [".net core"]:
        run_command(f'dotnet sonarscanner begin /k:"{project_key}" /d:sonar.token="{sonarqube_token}" /d:sonar.host.url="{SONARQUBE_URL}"', codebase_path)
        run_command("dotnet build --no-incremental", codebase_path)
        run_command(f'dotnet sonarscanner end /d:sonar.token="{sonarqube_token}"', codebase_path)

    elif language.lower() in ["java (maven)", "maven"]:
        run_command(f'mvn clean verify sonar:sonar -Dsonar.token={sonarqube_token} -Dsonar.host.url={SONARQUBE_URL} -Dsonar.projectKey={project_key}', codebase_path)

    elif language.lower() in ["java (gradle)", "gradle"]:
        run_command(f'gradle sonar -Dsonar.token={sonarqube_token} -Dsonar.host.url={SONARQUBE_URL} -Dsonar.projectKey={project_key}', codebase_path)

    elif language.lower() in ["python", "javascript", "typescript"]:
        run_command(f'"{SONARSCANNER_PATH}" -D"sonar.projectKey={project_key}" -D"sonar.sources=." -D"sonar.host.url={SONARQUBE_URL}" -D"sonar.token={sonarqube_token}"', codebase_path)

    else:
        print(f"⚠️ Unsupported language: {language}")
        sys.exit(1)

    print("✅ Scan completed successfully!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SonarQube Code Scanner")
    parser.add_argument("--codebase", required=True, help="Path to the codebase folder")
    parser.add_argument("--language", required=True, help="Programming language (e.g., .NET Framework, Java (Maven), Python)")
    parser.add_argument("--project-key", required=True, help="Project key for SonarQube")
    parser.add_argument("--token", required=True, help="SonarQube authentication token")

    args = parser.parse_args()

    scan_codebase(args.codebase, args.language, args.project_key, args.token)

