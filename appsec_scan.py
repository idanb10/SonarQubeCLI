import os
import subprocess
import yaml
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, request, render_template, jsonify
from werkzeug.utils import secure_filename
import zipfile
import shutil
import secrets
import traceback
import datetime
import tempfile  # Add this import for temporary directory handling

# Configure logging
def setup_logger():
    """Configure application logging"""
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'app.log'),
        maxBytes=10485760,  # 10MB
        backupCount=10
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    
    # Set up the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    return root_logger

# Initialize Flask app and logger
app = Flask(__name__)
logger = setup_logger()

app.config['UPLOAD_FOLDER'] = 'uploads'
# Remove the EXTRACTED_FOLDER config since we'll use tempfile instead
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size
app.secret_key = secrets.token_hex(16)

ALLOWED_EXTENSIONS = {'zip'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_project_key_from_filename(filename):
    """Extract project key from the zip filename."""
    logger.debug(f"Generating project key from filename: {filename}")
    project_key = os.path.splitext(filename)[0]
    project_key = ''.join(c if c.isalnum() else '_' for c in project_key)
    logger.debug(f"Generated project key: {project_key}")
    return project_key

def get_timestamped_directory():
    """Generate a timestamped directory name."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return timestamp

def load_sonarqube_config(config_path="config.yaml"):
    """Load SonarQube configuration from YAML file."""
    logger.info(f"Loading SonarQube configuration from {config_path}")
    try:
        with open(config_path, "r") as file:
            config = yaml.safe_load(file)
            logger.debug("Successfully loaded SonarQube configuration")
            return (
                config["sonarqube_url"], 
                config["sonarscanner_path"],
                config["sonarqube_token"]
            )
    except (yaml.YAMLError, KeyError, FileNotFoundError) as e:
        logger.error(f"Failed to load SonarQube configuration: {str(e)}")
        raise Exception(f"Error loading configuration: {str(e)}")

def run_command(command, cwd):
    """Execute shell commands and return output."""
    # Mask sensitive information in logs
    logged_command = command.replace('"sonar.token=', '"sonar.token=***')
    logger.info(f"Executing command in {cwd}: {logged_command}")
    
    try:
        process = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            check=True,
            text=True,
            capture_output=True
        )
        logger.debug(f"Command executed successfully")
        return True, process.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"Command execution failed: {str(e)}")
        return False, str(e)

def extract_zip(zip_path, extract_path):
    """Extract uploaded ZIP file to a directory."""
    logger.info(f"Extracting {zip_path} to {extract_path}")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Log zip contents before extraction
            zip_contents = zip_ref.namelist()
            logger.debug(f"ZIP contents: {zip_contents}")
            zip_ref.extractall(extract_path)
            
        # Log extracted contents
        extracted_contents = []
        for root, dirs, files in os.walk(extract_path):
            for file in files:
                extracted_contents.append(os.path.join(root, file))
        logger.debug(f"Extracted contents: {extracted_contents}")
    except Exception as e:
        logger.error(f"ZIP extraction failed: {str(e)}")
        raise
    
def find_solution_file(directory):
    """Recursively search for .sln files in the directory structure."""
    logger.debug(f"Searching for .sln file in {directory}")
    solution_files = []
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.sln'):
                solution_path = os.path.join(root, file)
                solution_files.append(solution_path)
                logger.debug(f"Found solution file: {solution_path}")
    
    return solution_files

def scan_codebase(codebase_path, language, project_key):
    """Run SonarQube scan based on the programming language."""
    logger.info(f"Starting code scan for project {project_key} ({language})")
    
    sonarqube_url, sonarscanner_path, sonarqube_token = load_sonarqube_config()
    
    if language.lower() in [".net framework"]:
        logger.debug("Configuring .NET Framework scan")
        solution_files = find_solution_file(codebase_path)
        
        if not solution_files:
            logger.error("No solution (.sln) file found")
            raise Exception("No solution (.sln) file found in the codebase directory or subdirectories.")
        
        # Use the first solution file found or let the user choose if multiple
        solution_file = solution_files[0]
        logger.info(f"Using solution file: {solution_file}")
        
        # Get directory containing the solution file for running commands
        solution_dir = os.path.dirname(solution_file)
        
        commands = [
            f'dotnet-sonarscanner begin /k:"{project_key}" /d:sonar.token="{sonarqube_token}" /d:sonar.host.url="{sonarqube_url}" /d:sonar.scm.disabled=true',
            f'msbuild "{os.path.basename(solution_file)}" /t:Rebuild /p:Configuration=Release',
            f'dotnet-sonarscanner end /d:sonar.token="{sonarqube_token}"'
        ]
        
        # Use solution_dir as the working directory
        cwd = solution_dir
    
    elif language.lower() in [".net core"]:
        logger.debug("Configuring .NET Core scan")
        solution_files = find_solution_file(codebase_path)
        
        if not solution_files:
            logger.error("No solution (.sln) file found")
            raise Exception("No solution (.sln) file found in the codebase directory or subdirectories.")
        
        # Use the first solution file found or let the user choose if multiple
        solution_file = solution_files[0]
        logger.info(f"Using solution file: {solution_file}")
        
        # Get directory containing the solution file for running commands
        solution_dir = os.path.dirname(solution_file)
        
        commands = [
            f'dotnet-sonarscanner begin /k:"{project_key}" /d:sonar.token="{sonarqube_token}" /d:sonar.host.url="{sonarqube_url}" /d:sonar.scm.disabled=true',
            "dotnet build --no-incremental",
            f'dotnet-sonarscanner end /d:sonar.token="{sonarqube_token}"'
        ]
        
        # Use solution_dir as the working directory
        cwd = solution_dir
    
    elif language.lower() in ["python", "javascript", "typescript"]:
        logger.debug(f"Configuring {language} scan")
        commands = [
            f'sonar-scanner -D"sonar.projectKey={project_key}" '
            f'-D"sonar.sources=." -D"sonar.host.url={sonarqube_url}" '
            f'-D"sonar.token={sonarqube_token}" -D"sonar.scm.disabled=true"'
        ]
        
        # Use the original codebase path for non-.NET languages
        cwd = codebase_path
    
    else:
        logger.error(f"Unsupported language: {language}")
        raise Exception(f"Unsupported language: {language}")

    outputs = []
    for cmd in commands:
        success, output = run_command(cmd, cwd)
        if not success:
            logger.error(f"Scan command failed")
            raise Exception(f"Command failed: {cmd}\nError: {output}")
        outputs.append(output)
    
    logger.info(f"Code scan completed successfully for project {project_key}")
    return outputs

@app.route('/')
def index():
    logger.info("Serving index page")
    return render_template('index.html')

@app.route('/scan', methods=['POST'])
def scan():
    logger.info("Received scan request")
    
    if 'file' not in request.files:
        logger.warning("No file uploaded in request")
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        logger.warning("Empty filename in request")
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        logger.warning(f"Invalid file type: {file.filename}")
        return jsonify({'error': 'Invalid file type. Please upload a ZIP file'}), 400

    # Create a temporary work directory
    work_dir = None
    temp_extract_dir = None
    
    try:
        # Create timestamped directory for uploaded file
        timestamp = get_timestamped_directory()
        upload_id = f"{timestamp}_{secrets.token_hex(4)}"
        
        # Set up directories
        work_dir = os.path.join(app.config['UPLOAD_FOLDER'], upload_id)
        os.makedirs(work_dir, exist_ok=True)
        logger.debug(f"Created working directory: {work_dir}")
        
        # Get form data
        user_provided_key = request.form.get('projectKey')
        original_filename = secure_filename(file.filename)
        
        # Use user-provided key if available, otherwise derive from filename
        if user_provided_key and user_provided_key.strip():
            project_key = user_provided_key.strip()
            logger.debug(f"Using user-provided project key: {project_key}")
        else:
            project_key = get_project_key_from_filename(original_filename)
            logger.debug(f"Generated project key from filename: {project_key}")
            
        # Get language from form data
        language = request.form.get('language')
        logger.info(f"Processing {language} project: {project_key}")
        
        # Save ZIP file to work directory
        zip_path = os.path.join(work_dir, original_filename)
        file.save(zip_path)
        logger.debug(f"Saved uploaded file to: {zip_path}")
        
        # Create temporary directory for extraction within the app's directory
        temp_dir_name = f"temp_extract_{project_key}_{upload_id}"
        temp_extract_dir = os.path.join(app.config['UPLOAD_FOLDER'], temp_dir_name)
        os.makedirs(temp_extract_dir, exist_ok=True)
        logger.debug(f"Created temporary extraction directory: {temp_extract_dir}")
        
        # Extract the zip file to the temporary directory
        extract_zip(zip_path, temp_extract_dir)
        
        # Run scan on the temporary directory
        scan_output = scan_codebase(temp_extract_dir, language, project_key)
        
        # Clean up work directory with the original ZIP file
        shutil.rmtree(work_dir)
        logger.debug(f"Cleaned up working directory: {work_dir}")
        
        logger.info(f"Scan completed successfully for project: {project_key}")
        return jsonify({
            'success': True,
            'message': f'Scan completed successfully for project: {project_key}',
            'project_key': project_key,
            'output': scan_output
        })
        
    except Exception as e:
        logger.error(f"Error during scan: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500
        
    finally:
        # Always clean up the temporary extraction directory
        if temp_extract_dir and os.path.exists(temp_extract_dir):
            try:
                shutil.rmtree(temp_extract_dir)
                logger.debug(f"Cleaned up temporary extraction directory: {temp_extract_dir}")
            except Exception as cleanup_error:
                logger.error(f"Error cleaning up temporary directory: {str(cleanup_error)}")
        
        # Clean up work directory if it exists and there was an error
        if work_dir and os.path.exists(work_dir):
            try:
                shutil.rmtree(work_dir)
                logger.debug(f"Cleaned up working directory: {work_dir}")
            except Exception as cleanup_error:
                logger.error(f"Error cleaning up work directory: {str(cleanup_error)}")

if __name__ == '__main__':
    # Ensure upload directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    logger.info("Starting Flask application")
    app.run(debug=True)