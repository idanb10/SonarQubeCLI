import os
import subprocess
import yaml
from flask import Flask, request, render_template, jsonify
from werkzeug.utils import secure_filename
import zipfile
import shutil
import secrets

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 16MB max file size
app.secret_key = secrets.token_hex(16)

ALLOWED_EXTENSIONS = {'zip'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_project_key_from_filename(filename):
    """Extract project key from the zip filename."""
    # Remove .zip extension and sanitize for SonarQube project key
    project_key = os.path.splitext(filename)[0]
    # Replace spaces and special characters with underscores
    project_key = ''.join(c if c.isalnum() else '_' for c in project_key)
    return project_key

def load_sonarqube_config(config_path="config.yaml"):
    """Load SonarQube configuration from YAML file."""
    try:
        with open(config_path, "r") as file:
            config = yaml.safe_load(file)
            return (
                config["sonarqube_url"], 
                config["sonarscanner_path"],
                config["sonarqube_token"]  # Add token to the returned values
            )
    except (yaml.YAMLError, KeyError, FileNotFoundError) as e:
        raise Exception(f"Error loading configuration: {str(e)}")

def run_command(command, cwd):
    """Execute shell commands and return output."""
    try:
        process = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            check=True,
            text=True,
            capture_output=True
        )
        return True, process.stdout
    except subprocess.CalledProcessError as e:
        return False, str(e)

def extract_zip(zip_path, extract_path):
    """Extract uploaded ZIP file to a temporary directory."""
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_path)

def scan_codebase(codebase_path, language, project_key):
    """Run SonarQube scan based on the programming language."""
    sonarqube_url, sonarscanner_path, sonarqube_token = load_sonarqube_config()
    
    if language.lower() in [".net framework"]:
        # Find .sln file
        solution_file = next((f for f in os.listdir(codebase_path) if f.endswith('.sln')), None)
        if not solution_file:
            raise Exception("No solution (.sln) file found in the codebase directory.")
        
        commands = [
            f'dotnet-sonarscanner begin /k:"{project_key}" /d:sonar.token="{sonarqube_token}" /d:sonar.host.url="{sonarqube_url}"',
            f'msbuild "{solution_file}" /t:Rebuild /p:Configuration=Release',
            f'dotnet-sonarscanner end /d:sonar.token="{sonarqube_token}"'
        ]
    
    elif language.lower() in [".net core"]:
        commands = [
            f'dotnet-sonarscanner begin /k:"{project_key}" /d:sonar.token="{sonarqube_token}" /d:sonar.host.url="{sonarqube_url}"',
            "dotnet build --no-incremental",
            f'dotnet-sonarscanner end /d:sonar.token="{sonarqube_token}"'
        ]
    
    elif language.lower() in ["python", "javascript", "typescript"]:
        commands = [
            f'"{sonarscanner_path}" -D"sonar.projectKey={project_key}" '
            f'-D"sonar.sources=." -D"sonar.host.url={sonarqube_url}" '
            f'-D"sonar.token={sonarqube_token}"'
        ]
    
    else:
        raise Exception(f"Unsupported language: {language}")

    outputs = []
    for cmd in commands:
        success, output = run_command(cmd, codebase_path)
        if not success:
            raise Exception(f"Command failed: {cmd}\nError: {output}")
        outputs.append(output)
    
    return outputs

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scan', methods=['POST'])
def scan():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Please upload a ZIP file'}), 400

    try:
        # Create unique working directory
        work_dir = os.path.join(app.config['UPLOAD_FOLDER'], secrets.token_hex(8))
        os.makedirs(work_dir, exist_ok=True)
        
        # Save and extract ZIP file
        original_filename = secure_filename(file.filename)
        zip_path = os.path.join(work_dir, original_filename)
        file.save(zip_path)
        extract_path = os.path.join(work_dir, 'extracted')
        extract_zip(zip_path, extract_path)
        
        # Get form data
        user_provided_key = request.form.get('projectKey')
        
        # Use user-provided key if available, otherwise derive from filename
        if user_provided_key and user_provided_key.strip():
            project_key = user_provided_key.strip()
        else:
            project_key = get_project_key_from_filename(original_filename)
        
        # Get language from form data
        language = request.form.get('language')
        
        # Run scan
        scan_output = scan_codebase(extract_path, language, project_key)
        
        # Clean up
        shutil.rmtree(work_dir)
        
        return jsonify({
            'success': True,
            'message': f'Scan completed successfully for project: {project_key}',
            'project_key': project_key,
            'output': scan_output
        })
        
    except Exception as e:
        # Clean up on error
        if 'work_dir' in locals():
            shutil.rmtree(work_dir)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Ensure upload directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)