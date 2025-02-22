# SonarQube Code Scanner
A web-based tool for running SonarQube scans on code projects. This application provides a simple interface for uploading code and initiating SonarQube analysis across multiple programming languages.

## Features

- Support for multiple programming languages:

  - Python
  - JavaScript
  - TypeScript
  - .NET Framework
  - .NET Core


- Automatic project key generation from filename
- Custom project key support
- ZIP file upload support
- Configurable SonarQube connection settings

## Prerequisites

- Python 3.8 or higher
- Flask
- SonarQube server (running and accessible)
- SonarQube Scanner installed locally

For .NET projects:

- .NET SDK
- dotnet-sonarscanner
- MSBuild (for .NET Framework projects)

## Installation

Clone the repository:

``` 
git clone https://github.com/idanb10/SonarQubeCLI

cd SonarQubeCLI 

pip install -r requirements.txt
```


Create a config.yaml file in the project root:
```
sonarqube_url: "http://your-sonarqube-server:9000"
sonarscanner_path: "/path/to/sonar-scanner"
sonarqube_token: "your-sonarqube-token-here"
```
## SonarQube Setup

1. Ensure your SonarQube server is running and accessible
2. Generate a token from SonarQube:

    - Log in to SonarQube
    - Go to User > My Account > Security
    - Generate a new token
    - Copy the token to your config.yaml file

## File Permissions:
Make sure the application has:

- Write permissions to the uploads directory
- Execute permissions for the SonarQube Scanner
- Read permissions for the config.yaml file

## Usage

1. Start the application:

```
python SonarQubeCLI.py
```
2. Open a web browser and navigate to http://localhost:5000

3. To scan a project:

    - (Optional) Enter a custom project key
    - Select the programming language
    - Upload your project as a ZIP file
    - Click "Start Scan"

4. Monitor the scan progress and view results in your SonarQube dashboard.