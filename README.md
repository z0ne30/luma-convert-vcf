# Launch Yard Contacts Manager

A Python tool for managing and organizing community contacts in VCF format from CSV input.

## Features

- Convert CSV contact data to VCF format
- Merge contact information from multiple events
- Customizable questionnaire configuration
- Automated note formatting and deduplication

## Installation

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Make the converter script executable:
   ```bash
   chmod +x convert.sh
   ```
## Directory Structure
- Contacts Input/ - Place your CSV files here
- event_vcfs/ - Contains event-specific VCF files
- master_contacts.vcf - Master database of all contacts

## Setup
1. Create your configuration file:

   ```bash
      cp question_config.yaml.example question_config.yaml
   ```
2. Edit question_config.yaml to customize:
   
   - Question mappings for your CSV headers
   - Event codes (e.g., WY for Weekly Yacht, YS for Yearly Summit)
   - Input/output directory settings
   - Fuzzy matching parameters

## Usage
### Using the Shell Script (Recommended)
   ```bash
   ./convert.sh "Contacts Input/YOUR_EVENT_NAME.csv"
   ```
### Using Python Directly
   ```bash
   python3 csv-vcf-converter.py "Contacts Input/YOUR_EVENT_NAME.csv"
   ```
The tool will:
- Process the CSV data according to your configuration
- Create an event-specific VCF in event_vcfs/
- Update the master contacts database


## Event Naming Convention
Files should follow the format: [Event Type] [Details] [Date].csv Examples:

- Yard Sale Harvard Guests Feb 27 2025.csv
- Wine Yard Boston Dec 03 2024.csv
Supported event codes:

- YS - Yard Sale events
- WY - Wine Yard events
- OH - Open House events
## Example Workflow
1. Place your CSV file in the Contacts Input directory
2. Run the converter:
   ```bash
   ./convert.sh "Contacts Input/Yard Sale Harvard Guests Feb 27 2025.csv"
   ```
3. Find your outputs in:
- event_vcfs/ for event-specific contacts
- master_contacts.vcf for the merged database

## Tips
- Always check question_config.yaml mappings match your CSV headers
- Use consistent event codes in your file naming
- Back up master_contacts.vcf regularly

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License
MIT


This updated README:
1. Adds the shell script usage
2. Clarifies the directory structure
3. Provides more detailed setup instructions
4. Explains the event naming convention
5. Shows actual example commands
6. Includes tips for usage
7. Makes the workflow more explicit