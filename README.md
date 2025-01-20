# Contact Converter

Converts Luma CSV exports to VCF format with event history tracking.

## Setup

1. Create required directories:
   ```bash
   mkdir -p "Contacts Input"
   mkdir -p "VCF Output"
   mkdir -p "Contact Snapshots"
   ```

2. Place CSV files in `Contacts Input` directory

3. Ensure `question_config.yaml` is configured for your events

## Usage

### Process a single new event:
bash
python csv-vcf-converter.py "Event Name.csv" --verbose

### Process multiple historical events:
Process files in chronological order to build contact history:

bash
python csv-vcf-converter.py "older-event.csv"
python csv-vcf-converter.py "newer-event.csv"

### Output Files
- `Contact Snapshots/{date}_{event_code}_snapshot.vcf`: Individual event snapshots
- `Contact Snapshots/master_contacts.vcf`: Complete contact list with full history
- `Contact Snapshots/contact_history.json`: Processing history and contact data

## Adding New Event Types

1. Edit `question_config.yaml`:
   ```yaml
   events:
     types:
       NEW_EVENT:
         name: "New Event Name"
         code: "NE"
         identifiers: ["New Event", "NE"]
         default_questions:
           - "linkedin"
           - "role_type"
   ```

2. Add any new questions under `events.questions`

## Contact Format

Contacts are stored with:
- Basic info (name, email, phone)
- LinkedIn URL
- Structured notes showing:
  - All events attended
  - Latest professional info
  - Latest needs/interests
  - Community involvement
  - Aspirational goals

## Importing to Apple Contacts

1. Open Contacts app
2. File > Import
3. Select `master_contacts.vcf`
4. Choose to replace existing contacts when prompted
