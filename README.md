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

## Configuration

Copy `question_config.yaml.example` to `question_config.yaml` and customize it for your needs. The configuration includes:

- Sections and questions
- Community roles
- Event codes

See the example file for detailed documentation.

## Usage

1. Prepare your CSV file with contact information
2. Run the converter:
   ```bash
   python csv-vcf-converter.py input.csv output.vcf
   ```
3. The tool will:
   - Process the CSV data
   - Merge with existing VCF contacts if present
   - Generate a new VCF file with formatted notes

## Example Workflow

1. After each event, collect responses in a CSV file
2. Run the converter to update your master contacts
3. Import the VCF file into your contact management system

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License

[MIT](https://choosealicense.com/licenses/mit/)
