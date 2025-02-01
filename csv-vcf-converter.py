# csv-vcf-converter.py
import csv
import re
from types import NoneType
import yaml
import phonenumbers
from fuzzywuzzy import fuzz
from pathlib import Path
from datetime import datetime


class ContactProcessor:
    def __init__(self, config_path):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        print("LOADED MAPPINGS:", self.config['mappings'])
        
        # Fuzzy matching configuration
        fuzzy_config = self.config.get('fuzzy_matching', {})
        self.name_similarity_threshold = fuzzy_config.get('name_threshold', 85)
        self.phone_match_required = fuzzy_config.get('phone_match_required', True)
        self.name_weight = fuzzy_config.get('name_weight', 0.7)
        self.phone_weight = fuzzy_config.get('phone_weight', 0.3)
        
        # Initialize contact stores
        self.master_contacts = self._load_master_contacts()
        self.phone_cache = {}
    
    def _find_existing_contact(self, new_contact):
        # Tier 1: Exact email match (regardless of name)
        for existing in self.master_contacts.values():
            if new_contact['email'] == existing['email']:
                return existing
        
        # Tier 2: Phone match + name similarity
        phone_matches = []
        for existing in self.master_contacts.values():
            if new_contact['phone'] and existing['phone']:
                if new_contact['phone'] == existing['phone']:
                    name_score = fuzz.ratio(new_contact['name'].lower(), 
                                        existing['name'].lower())
                    if name_score >= self.name_similarity_threshold:
                        phone_matches.append((existing, name_score))
        
        if phone_matches:
            # Return best name match among phone matches
            return max(phone_matches, key=lambda x: x[1])[0]
        
        # Tier 3: Name similarity alone (with relaxed threshold)
        name_threshold = max(self.name_similarity_threshold - 15, 50)
        best_name_match = None
        best_name_score = 0
        
        for existing in self.master_contacts.values():
            name_score = fuzz.ratio(new_contact['name'].lower(),
                                existing['name'].lower())
            if name_score > best_name_score and name_score >= name_threshold:
                best_name_match = existing
                best_name_score = name_score
        
        return best_name_match

    def _load_master_contacts(self):
        master_path = Path(self.config['output']['master_file'])
        if not master_path.exists():
            return {}
            
        # Implement VCF parsing logic
        return {}  # Placeholder

    def process_event(self, csv_path):
        event_info = self._parse_filename(csv_path.name)
        contacts = self._read_csv(csv_path, event_info)
        self._update_master(contacts)
        self._write_snapshot(contacts, event_info)

    def _parse_filename(self, filename):
        """Parse filename to extract event code and date"""
        # Remove the .csv extension
        name = filename.replace('.csv', '')
        
        # Find matching event pattern
        event_code = None
        for event_type, rules in self.config['event_mappings'].items():
            if re.match(rules['match'], name):
                event_code = rules['code']
                break
        
        if not event_code:
            raise ValueError(f"Unrecognized event pattern in filename: {filename}")
        
        # Extract date components
        parts = name.split()
        month, day, year = parts[-3:]
        
        # Convert month using config mapping
        month_num = self.config['date_format']['month_map'].get(month, '00')
        
        # Format as code-MM-DD-YY
        code_date = f"{event_code}-{month_num}-{day}-{year[-2:]}"
        
        return {
            'event_name': ' '.join(parts[:-3]),
            'date': ' '.join(parts[-3:]),
            'code': code_date
        }
            
    def _read_csv(self, csv_path, event_info):
        contacts = []
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['approval_status'] != 'approved':
                    continue
                
                contact = self._process_row(row)
                contact['event_info'] = event_info  # Add event_info to the contact
                contacts.append(contact)
        return contacts

    def _process_row(self, row):
        # Normalize contact info
        contact = {
            'name': row['name'].strip(),
            'email': row['email'].lower().strip(),
            'phone': self._normalize_phone(row.get('phone_number', '')),
            'event_data': {}
        }

        # Process custom questions
        for csv_header, vcf_key in self.config['mappings'].items():
            if csv_header in row and row[csv_header].strip():
                contact['event_data'][vcf_key] = row[csv_header].strip()
        
        print("RAW LINKEDIN VALUE:", row.get('LINKEDIN'))
        
        return contact

    def _normalize_phone(self, phone):
        try:
            return phonenumbers.format_number(
                phonenumbers.parse(phone, 'US'),
                phonenumbers.PhoneNumberFormat.E164
            )
        except:
            return phone.strip()
        
    def _update_master(self, new_contacts):
        """Update master contacts with new event data"""
        for new_contact in new_contacts:
            # Find existing contact using email + name fuzzy matching
            existing = self._find_existing_contact(new_contact)
            
            if existing:
                # Merge notes and LinkedIn data
                merged_note = self._merge_notes(
                    existing['note'], 
                    new_contact['event_data'],
                    new_contact['event_info']
                )
                existing.update({
                    'phone': new_contact['phone'] or existing['phone'],
                    'note': merged_note,
                    'event_data': {
                        **existing.get('event_data', {}),
                        'LINKEDIN': new_contact['event_data'].get('LINKEDIN', 
                            existing.get('event_data', {}).get('LINKEDIN'))
                    }
                })
            else:
                # Create new contact entry
                vcf_id = f"{new_contact['email']}-{hash(new_contact['name'])}"
                self.master_contacts[vcf_id] = {
                    'name': new_contact['name'],
                    'email': new_contact['email'],
                    'phone': new_contact['phone'],
                    'note': self._merge_notes('', new_contact['event_data'], new_contact['event_info']),
                    'event_data': new_contact['event_data']
                }

        print("MERGING LINKEDIN:", new_contact['event_data'].get('LINKEDIN'))
            
    def _merge_notes(self, existing_note, new_event_data, event_info):
        """Merge new event data into existing note field"""
        if existing_note:
            # Split existing note into events
            events = existing_note.split('__________')
            # Check if event already exists
            event_code_date = f"({event_info['code']})"
            if any(event_code_date in event for event in events):
                return existing_note
            else:
                # Filter out LinkedIn from note details
                filtered_data = {k:v for k,v in new_event_data.items() if k != 'LINKEDIN'}
                details = ' -- '.join([f"{key}:{value}" for key, value in filtered_data.items()])
                return f"{existing_note}__________{event_code_date} -- {details}"
        else:
            # Format new note if no existing note
            filtered_data = {k:v for k,v in new_event_data.items() if k != 'LINKEDIN'}
            details = ' -- '.join([f"{key}:{value}" for key, value in filtered_data.items()])
            return f"({event_info['code']}) -- {details}"

    def _write_snapshot(self, contacts, event_info):
        """Write event-specific VCF snapshot"""
        output_dir = Path(self.config['output']['snapshot_dir'])
        output_dir.mkdir(exist_ok=True)
        
        filename = f"{event_info['code']}.vcf"
        with open(output_dir / filename, 'w') as f:
            for contact in contacts:
                f.write(self._generate_vcf(contact, event_info))

    def _generate_vcf(self, contact, event_info=None):
        """Generate VCF entry for a contact"""
        vcf_lines = [
            "BEGIN:VCARD",
            "VERSION:3.0",
            f"N:{contact['name'].split()[-1]};{contact['name'].split()[0]};;;",
            f"FN:{contact['name']}",
            f"EMAIL:{contact['email']}",
            f"TEL;TYPE=CELL:{contact['phone']}",
        ]
        
        event_data = contact.get('event_data', {})
        if 'LINKEDIN' in event_data:
            linkedin_url = event_data['LINKEDIN']
            
            # Normalize URL format
            if linkedin_url.startswith('www.linkedin.com'):
                linkedin_url = f"https://{linkedin_url}"
            elif linkedin_url.startswith('linkedin.com'):
                linkedin_url = f"https://www.{linkedin_url}"
            # Ensure www. prefix
            if '//linkedin.com' in linkedin_url:
                linkedin_url = linkedin_url.replace('//linkedin.com', '//www.linkedin.com')
            
            vcf_lines.append(f"URL;TYPE=WORK:{linkedin_url}")
        
        print("FINAL LINKEDIN VALUE:", event_data.get('LINKEDIN'))
        
        # Add note
        existing_note = contact.get('note', '')
        if event_info:
            note = self._merge_notes(existing_note, contact['event_data'], event_info)
        else:
            note = existing_note
        vcf_lines.append(f"NOTE:{note}")
        
        vcf_lines.append("END:VCARD")
        return '\n'.join(vcf_lines) + '\n'

    # Update _load_master_contacts to parse existing VCF
    def _load_master_contacts(self):
        master_path = Path(self.config['output']['master_file'])
        if not master_path.exists():
            return {}

        contacts = {}
        with open(master_path, 'r') as f:
            current_contact = {}
            for line in f:
                line = line.strip()
                if line.startswith('BEGIN:VCARD'):
                    current_contact = {}
                elif line.startswith('END:VCARD'):
                    email = current_contact.get('email', '')
                    if email:
                        contacts[email] = current_contact
                elif line.startswith('FN:'):
                    current_contact['name'] = line[3:]
                elif line.startswith('EMAIL:'):
                    current_contact['email'] = line[6:]
                elif line.startswith('TEL;'):
                    current_contact['phone'] = line.split(':')[-1]
                elif line.startswith('NOTE:'):
                    current_contact['note'] = line[5:]
        return contacts


    def process_event_directory(self, input_dir):
        """Process all CSV files in directory sorted by event date"""
        input_path = Path(input_dir)
        csv_files = []
        
        # Find and parse CSV files with dates
        for csv_file in input_path.glob('*.csv'):
            date_str = ' '.join(csv_file.stem.split()[-3:])  # Get last 3 parts
            try:
                event_date = datetime.strptime(date_str, "%b %d %Y")
                csv_files.append((event_date, csv_file))
            except ValueError:
                continue
        
        # Sort by date and process
        for date, csv_path in sorted(csv_files, key=lambda x: x[0]):
            print(f"\nProcessing {csv_path.name} ({date.strftime('%Y-%m-%d')}")
            self.process_event(csv_path)
            
        print("\nBatch processing complete")

        self._save_master_contacts()  # Add this line
        print(f"Master contacts saved to {self.config['output']['master_file']}")
   
    def _save_master_contacts(self):
        master_path = Path(self.config['output']['master_file'])
        master_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(master_path, 'w') as f:
            for contact in self.master_contacts.values():
                f.write(self._generate_vcf(contact))

if __name__ == "__main__":
    processor = ContactProcessor('question_config.yaml')
    input_dir = "Contacts Input"
    processor.process_event_directory(input_dir)