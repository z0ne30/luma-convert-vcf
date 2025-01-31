"""
CSV to VCF Contact Converter
===========================

This script processes CSV files exported from Luma and converts them to VCF format,
maintaining contact history across multiple events. It supports different event types
and automatically merges contact information when the same person attends multiple events.

Features:
    - Processes Luma CSV exports
    - Maintains contact history across events
    - Creates event-specific snapshots
    - Merges contact information intelligently
    - Structures notes by categories
    - Handles different event types (WY/YS)

Usage:
    python csv-vcf-converter.py "Event Name.csv" --verbose

Directory Structure:
    Contacts Input/     - Place CSV files here
    Contact Snapshots/  - Historical snapshots and master VCF

Configuration:
    See question_config.yaml for event types and field mappings
"""

import csv
from datetime import datetime
import sys
import os
import re
import yaml
import json
import traceback
import logging
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('contact_converter.log'),
        logging.StreamHandler()
    ]
)

def handle_errors(func):
    """
    Decorator for consistent error handling and logging.
    
    Args:
        func: Function to wrap
        
    Returns:
        Wrapped function with error handling
    
    Logs errors and returns None on failure.
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logging.error(f"Error in {func.__name__}: {str(e)}")
            if '--verbose' in sys.argv:
                logging.debug(traceback.format_exc())
            return None
    return wrapper

@dataclass
class Contact:
    """
    Represents a contact with all their information.
    
    Attributes:
        name (str): Full name
        email (str): Email address (unique identifier)
        phone (str): Phone number
        linkedin (str): LinkedIn profile URL
        answers (Dict[str, str]): Responses to event questions
        approval_status (str): 'approved' or 'declined'
        notes (str): Formatted notes including event history
    """
    name: str
    email: str
    phone: str
    linkedin: str
    answers: Dict[str, str]
    approval_status: str
    notes: str
    
    @property
    def first_name(self) -> str:
        """Extract first name from full name"""
        return self.name.split(' ')[0] if self.name else ''
    
    @property
    def last_name(self) -> str:
        """Extract last name from full name"""
        parts = self.name.split(' ', 1)
        return parts[1] if len(parts) > 1 else ''
    
    def is_valid(self, required_fields: List[str]) -> bool:
        """
        Check if contact has all required fields.
        
        Args:
            required_fields: List of field names that must have values
            
        Returns:
            bool: True if all required fields have values
        """
        return all(getattr(self, field, None) for field in required_fields)

@dataclass
class Event:
    """Class to represent an event"""
    name: str
    code: str
    date: datetime
    questions: List[str]
    
    @property
    def event_code(self) -> str:
        """Generate standardized event code (e.g., WY-2025-01-19)"""
        return f"{self.code}-{self.date.strftime('%Y-%m-%d')}"
    
    def format_name(self) -> str:
        """Format event name for display"""
        return f"{self.event_code} ({self.name})"

class ContactProcessor:
    """Handles CSV processing and VCF generation"""
    def __init__(self, config_file: str):
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing ContactProcessor")
        
        with open(config_file, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
            self.logger.debug(f"Loaded configuration from {config_file}")
        
        # Set up directories from config
        self.input_dir = self.config['core']['directories']['input']
        self.snapshot_dir = Path(self.config['core']['directories']['snapshots'])
        self.logger.info(f"Set up directories: input={self.input_dir}, snapshot={self.snapshot_dir}")
    
    @handle_errors
    def identify_event(self, filename: str) -> Optional[Event]:
        """Identify event type from filename"""
        try:
            # Extract date
            date = self._extract_date(filename)
            if not date:
                return None
            
            # Match against event types
            for code, event_type in self.config['events']['types'].items():
                for identifier in event_type['identifiers']:
                    if identifier.lower() in filename.lower():
                        return Event(
                            name=event_type['name'],
                            code=code,
                            date=date,
                            questions=event_type.get('questions', [])
                        )
        
            return None
            
        except Exception as e:
            self.logger.error(f"Error identifying event: {str(e)}")
        return None

    @handle_errors
    def process_csv(self, filename: str) -> List[Contact]:
        """Process a CSV file and generate contacts"""
        self.logger.info(f"Processing CSV file: {filename}")
        
        event = self.identify_event(filename)
        if not event:
            msg = f"Could not identify event type from {filename}"
            self.logger.error(msg)
            raise ValueError(msg)

        contacts = []
        declined_contacts = []  # Track declined contacts
        
        with open(Path(self.input_dir) / filename, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            ignore_fields = set(self.config['ignore_fields'])
            row_count = 0
            
            for row in reader:
                row_count += 1
                self.logger.debug(f"Processing row {row_count}")
                contact = self._process_row(row, ignore_fields)
                
                # Check approval status
                if contact:
                    if contact.approval_status == 'approved':
                        contacts.append(contact)
                        self.logger.debug(f"Added contact: {contact.email}")
                    elif contact.approval_status in ['declined', 'pending']:  # Handle both declined and pending
                        declined_contacts.append(contact)
                        self.logger.debug(f"Added declined/pending contact: {contact.email}")
                else:
                    self.logger.warning(f"Skipped invalid contact in row {row_count}")
        
        # Write declined contacts to txt file
        if declined_contacts:
            # Create Archive Outputs directory if it doesn't exist
            archive_dir = Path('Archive Outputs')
            archive_dir.mkdir(parents=True, exist_ok=True)
            
            # Format filename like: 01-31-2025YS_declined.txt
            declined_file = archive_dir / f"{event.date.strftime('%m-%d-%Y')}{event.code}_declined.txt"
            
            with open(declined_file, 'w', encoding='utf-8') as f:
                for contact in declined_contacts:
                    # Write name, email and phone, handling empty fields
                    name = contact.name if contact.name else 'No Name'
                    email = contact.email if contact.email else 'No Email'
                    phone = contact.phone if contact.phone else 'No Phone'
                    status = contact.approval_status.upper()
                    f.write(f"{name}, {email}, {phone}, {status}\n")
            
            self.logger.info(f"Wrote {len(declined_contacts)} declined/pending contacts to {declined_file}")
        
        self.logger.info(f"Processed {len(contacts)} valid contacts from {filename}")
        return contacts

    def _process_row(self, row: Dict, ignore_fields: set) -> Optional[Contact]:
        """Process a single CSV row into a Contact"""
        cleaned_row = {k.replace('\ufeff', ''): v.strip() for k, v in row.items() if v}
        
        # Check approval status first
        approval_status = cleaned_row.get('approval_status', 'pending').lower()
        if approval_status != 'approved':
            # Store minimal info for declined contacts
            return Contact(
                name=cleaned_row.get('name', ''),
                email=cleaned_row.get('email', ''),
                phone=cleaned_row.get('phone_number', ''),
                linkedin='',  # Empty for declined contacts
                answers={},  # Empty dict for declined contacts
                approval_status=approval_status,
                notes=''  # Empty notes for declined contacts
            )
        
        # Process approved contacts fully
        answers = {}
        for field, value in cleaned_row.items():
            if (field not in ignore_fields and 
                field not in ['name', 'email', 'phone_number', 'approval_status'] and 
                value):
                answers[field] = value
        
        contact_data = {
            'name': cleaned_row.get('name', ''),
            'email': cleaned_row.get('email', ''),
            'phone': cleaned_row.get('phone_number', ''),
            'linkedin': cleaned_row.get('What is your LinkedIn profile?', ''),
            'answers': answers,
            'approval_status': 'approved',
            'notes': ''  # Initialize with empty notes
        }
        
        return Contact(**contact_data)

    def _format_notes(self, contact: Contact, event: Optional[Event] = None) -> str:
        """Format contact notes with proper spacing"""
        # Get note formatting config
        note_config = self.config['notes']['format']
        
        # Initialize event groups
        event_groups = {}
        
        # Parse existing notes into event groups
        if contact.notes:
            
            current_event = None
            for line in contact.notes.split('  '):  # Split on double spaces
                line = line.strip()
                if line.startswith('EVENT:'):
                    current_event = line
                    event_groups[current_event] = []
                elif current_event and line:
                    event_groups[current_event].append(line)
        
        # Format new event info
        if isinstance(event, Event):
            event_str = f"EVENT: {note_config['event_format'].format(code=event.code, date=event.date.strftime('%Y-%m-%d'), name=event.name)}"
            
            # Get sections for this event
            sections = self._get_section_values(contact, event)
            event_notes = []
            
            # Always add ROLE first if it exists
            if sections.get('PROFESSIONAL'):
                roles = [note for note in sections['PROFESSIONAL'] if note.startswith('ROLE:')]
                if roles:
                    event_notes.extend(sorted(roles))
            
            # Add other sections in priority order
            for section in sorted(self.config['notes']['sections'], key=lambda x: x.get('priority', 99)):
                section_name = section['name']
                if section_name != 'PROFESSIONAL' and sections.get(section_name):  # Skip PROFESSIONAL since we handled ROLEs
                    event_notes.extend(sorted(sections[section_name]))
            
            event_groups[event_str] = event_notes
        
        # Format all events
        result = []
        for event_str, notes in event_groups.items():
            event_line = [event_str]
            if notes:
                event_line.extend(notes)
            result.append('  '.join(event_line))
        
        # Join events with 10 spaces between them
        return '          '.join(result)

    def _extract_date(self, filename: str) -> Optional[datetime]:
        """Extract date from filename using various patterns"""
        filename = os.path.splitext(filename)[0]
        
        patterns = [
            (r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{2}\s+\d{4}', '%b %d %Y'),
            (r'\d{2}-\d{2}-\d{4}', '%m-%d-%Y'),
        ]
        
        for pattern, date_format in patterns:
            if match := re.search(pattern, filename):
                try:
                    return datetime.strptime(match.group(), date_format)
                except ValueError:
                    continue
        return None

    def _format_section_content(self, section_name: str, answers: Dict, questions: List[str]) -> str:
        """Format content for a notes section"""
        content = set()  # Changed from list to set to prevent duplicates
        section_config = self.config['events']['questions']
        
        for question_id in questions:
            question = section_config.get(question_id, {})
            if question.get('category', '').upper() == section_name:
                for pattern in question['patterns']:
                    for field, value in answers.items():
                        if pattern.lower() in field.lower():
                            content.add(f"{question['note_prefix']}: {value}")  # Using add instead of append
                            break  # Break after first match to prevent duplicates
        
        return '\n'.join(sorted(content)) if content else ''  # Sort for consistent ordering

    def _format_vcf_entry(self, contact: Contact, event: Event) -> str:
        """Format a single VCF entry"""
        vcf = []
        vcf.append("BEGIN:VCARD")
        vcf.append(f"VERSION:{self.config['core']['vcf']['version']}")
        vcf.append(f"N:{contact.last_name};{contact.first_name};;;")
        vcf.append(f"EMAIL:{contact.email}")
        vcf.append(f"TEL:{contact.phone}")
        
        # Format LinkedIn URL as Work URL
        if contact.linkedin:
            vcf.append(f'URL;TYPE=WORK:{contact.linkedin}')
        
        # Format notes (LinkedIn is handled separately above)
        notes = self._format_notes(contact, event)
        if notes:
            vcf.append(f"NOTE:{notes}")
        
        vcf.append("END:VCARD\n")
        return "\n".join(vcf)

    def _get_section_values(self, contact: Contact, event: Optional[Event] = None) -> Dict[str, Set[str]]:
        """Get values for each section from contact answers"""
        try:
            sections = {}
            for section in self.config['notes']['sections']:
                sections[section['name']] = set()
            
            if not contact.answers or not event:
                return sections
            
            # Get questions for this event type
            event_questions = []
            if event:
                event_type = self.config['events']['types'].get(event.code, {})
                event_questions = event_type.get('questions', [])
            
            # Process each question
            for question_id in event_questions:
                question = self.config['events']['questions'].get(question_id, {})
                category = question.get('category', '').upper()  # Ensure uppercase
                note_prefix = question.get('note_prefix', '')
                
                # Skip only LinkedIn fields
                if 'linkedin' in question_id.lower():
                    continue
                
                found_match = False
                for pattern in question.get('patterns', []):
                    if found_match:
                        break
                        
                    for field, value in contact.answers.items():
                        if any(skip in field.lower() for skip in ['linkedin', 'url', 'profile']):
                            continue
                            
                        if pattern.lower() in field.lower():
                            # Special handling for roles - keep them together
                            if question_id == 'rsvp_role':
                                sections['PROFESSIONAL'].add(f"ROLE: {value}")  # Keep original value with comma
                            else:
                                # Transform value if mappings exist
                                if 'transform' in question:
                                    value = question['transform'].get(value, value)
                                    
                                # Handle other fields
                                if ',' in value:
                                    values = [v.strip() for v in value.split(',')]
                                    for v in values:
                                        sections[category].add(f"{note_prefix}: {v}")
                                else:
                                    sections[category].add(f"{note_prefix}: {value}")
                            found_match = True
                            break

            return sections
            
        except Exception as e:
            self.logger.error(f"Error getting section values: {str(e)}")
            return {}

    def _merge_contact_data(self, old: Optional[Contact], new: Contact, event_code: str) -> Contact:
        """Smart merge of contact data based on configuration"""
        
        def is_valid_linkedin_url(url: str) -> bool:
            if not url:
                return False
            url = url.lower()
            return (
                url.startswith('http') and 
                ('linkedin.com' in url or 'linked.in' in url)
            )

        if old:  # If contact exists, keep their data and only append new event info
            merged = Contact(
                name=old.name,
                email=old.email,
                phone=old.phone,
                linkedin=old.linkedin,
                approval_status=old.approval_status,
                answers=old.answers,
                notes=old.notes  # Initialize with old notes
            )
            
            # Extract new event info from new contact's notes
            if new.notes:
                event_info = ""
                for line in new.notes.split("\n"):
                    if line.startswith("EVENT:"):
                        event_info = line.split("EVENT:", 1)[1].strip()
                        break
                
                # Only append if this event isn't already in notes
                if event_info and event_code not in old.notes:
                    if old.notes:
                        merged.notes = f"{old.notes}-----EVENT: {event_info}"  # 5 dashes between events
                    else:
                        merged.notes = f"EVENT: {event_info}"
                else:
                    merged.notes = old.notes  # Keep old notes if no new notes
            
        else:  # New contact - use all their info
            merged = Contact(
                name=new.name,
                email=new.email,
                phone=new.phone,
                linkedin=new.linkedin if is_valid_linkedin_url(new.linkedin) else '',
                approval_status=new.approval_status,
                answers=new.answers,
                notes=new.notes
            )

        return merged

    def _load_contacts_from_vcf(self, vcf_path: Path) -> Dict[str, Contact]:
        """Load contacts from a VCF file"""
        contacts = {}
        if not vcf_path.exists():
            return contacts
        
        try:
            current_contact = None
            with open(vcf_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('BEGIN:VCARD'):
                        current_contact = {}
                    elif line.startswith('END:VCARD') and current_contact:
                        if 'email' in current_contact:
                            # Parse name components
                            name_parts = current_contact.get('n', ';;;;').split(';')
                            last_name = name_parts[0]
                            first_name = name_parts[1]
                            full_name = current_contact.get('fn', f"{first_name} {last_name}".strip())
                            
                            contacts[current_contact['email']] = Contact(
                                name=full_name,
                                email=current_contact['email'],
                                phone=current_contact.get('tel', ''),
                                linkedin=current_contact.get('url', ''),
                                notes=current_contact.get('note', ''),
                                approval_status='approved',  # These are from VCF so they were approved
                                answers={}  # Initialize with empty answers dict since VCF doesn't store this
                            )
                        current_contact = None
                    elif current_contact is not None and ':' in line:
                        key, value = line.split(':', 1)
                        key = key.split(';')[0].lower()  # Handle TYPE parameters
                        current_contact[key] = value
        
            return contacts
        except Exception as e:
            self.logger.error(f"Error loading VCF {vcf_path}: {str(e)}")
            return {}

    def _save_master_vcf(self, contacts: Dict[str, Contact]):
        """Save contacts to master VCF file"""
        master_path = self.snapshot_dir / 'master_contacts.vcf'
        self.logger.info(f"Saving master VCF to {master_path}")
        
        try:
            with open(master_path, 'w', encoding='utf-8') as f:
                for contact in sorted(contacts.values(), key=lambda x: x.email):
                    if contact.approval_status == 'approved':  # Only save approved contacts
                        f.write("BEGIN:VCARD\n")
                        f.write("VERSION:3.0\n")
                        f.write(f"N:{contact.last_name};{contact.first_name};;;\n")
                        f.write(f"FN:{contact.name}\n")
                        f.write(f"EMAIL:{contact.email}\n")
                        if contact.phone:
                            f.write(f"TEL:{contact.phone}\n")
                        if contact.linkedin:
                            f.write(f"URL;TYPE=WORK:{contact.linkedin}\n")
                        if contact.notes:
                            f.write(f"NOTE:{contact.notes}\n")
                        f.write("END:VCARD\n\n")
            
            self.logger.info(f"Successfully saved {len(contacts)} contacts to master VCF")
        except Exception as e:
            self.logger.error(f"Error saving master VCF: {str(e)}")

    def _save_contacts_to_vcf(self, contacts: List[Contact], output_path: Path, event: Optional[Event] = None):
        """Save contacts to a VCF file"""
        self.logger.info(f"Saving {len(contacts)} contacts to {output_path}")
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                for contact in contacts:
                    if contact.approval_status == 'approved':  # Only save approved contacts
                        f.write(self._format_vcf_entry(contact, event))
            
            self.logger.info(f"Successfully saved contacts to {output_path}")
        except Exception as e:
            self.logger.error(f"Error saving contacts to {output_path}: {str(e)}")

class ContactManager:
    """Manages contact history and snapshots"""
    def __init__(self, config_file: str):
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing ContactManager")
        
        self.processor = ContactProcessor(config_file)
        self.config = self.processor.config
        
        # Set up snapshot directory from config
        self.snapshot_dir = Path(self.config['core']['directories']['snapshots'])
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Set up snapshot directory: {self.snapshot_dir}")

        # Load processing history
        self.history = self._load_history()

    def process_new_csv(self, filename: str):
        """Process new CSV file and update contacts"""
        try:
            self.logger.info(f"Processing new CSV: {filename}")
            
            # Check if file was already processed
            if filename in self.history['processed_files']:
                self.logger.warning(f"File already processed: {filename}")
                return False
            
            # Update current file in history
            self.history['current_file'] = filename
            self._save_history()
            
            # Create snapshot
            snapshot_path = self._create_snapshot(filename)
            if not snapshot_path:
                return False
                
            # Update master file
            self._update_master_from_snapshots()
        
            # Update history after successful processing
            self._update_history(filename, str(snapshot_path))
            return True
            
        except Exception as e:
            self.logger.error(f"Error processing CSV: {str(e)}")
            return False

    def _create_snapshot(self, filename: str) -> Optional[Path]:
        """Create VCF snapshot from CSV file"""
        try:
            # Identify event type
            event = self.processor.identify_event(filename)
            if not event:
                self.logger.error(f"Could not identify event type: {filename}")
                return None
            
            # Generate snapshot filename
            snapshot_name = self.config['core']['processing']['snapshot_format'].format(
            date=event.date.strftime('%Y-%m-%d'),
            event_code=event.code
        )
            snapshot_path = self.snapshot_dir / snapshot_name
            
            # Process CSV to VCF
            contacts = self.processor.process_csv(filename)
            if not contacts:
                return None
                
            # Save snapshot using the correct method
            self.processor._save_contacts_to_vcf(contacts, snapshot_path, event)
            self.logger.info(f"Created snapshot: {snapshot_path}")
            
            return snapshot_path
            
        except Exception as e:
            self.logger.error(f"Error creating snapshot: {str(e)}")
            return None

    def _update_master_from_snapshots(self):
        """Update master VCF by merging all snapshots"""
        master_path = self.snapshot_dir / 'master_contacts.vcf'
        self.logger.info(f"Updating master VCF at: {master_path}")
        
        # Load existing master contacts
        master_contacts = {}
        if master_path.exists():
            master_contacts = self.processor._load_contacts_from_vcf(master_path)
        
        # Get all snapshots
        all_snapshots = sorted(self.snapshot_dir.glob('*_snapshot.vcf'))
        processed_snapshots = set(self.history.get('processed_snapshots', []))
        new_snapshots = [s for s in all_snapshots if str(s) not in processed_snapshots]
        
        if not new_snapshots:
            self.logger.info("No new snapshots to process")
            return
            
        # Process each new snapshot chronologically
        for snapshot_path in sorted(new_snapshots):
            try:
                self.logger.info(f"Processing snapshot: {snapshot_path.name}")
                
                # Parse event info from snapshot filename
                date_str = snapshot_path.stem.split('_')[0]
                event_code = snapshot_path.stem.split('_')[1]
                event_id = f"{event_code}-{date_str}"
                
                # Load and merge contacts
                snapshot_contacts = self.processor._load_contacts_from_vcf(snapshot_path)
                for email, contact in snapshot_contacts.items():
                    if contact.approval_status == 'approved':  # Only merge approved contacts
                        if email in master_contacts:
                            master_contacts[email] = self.processor._merge_contact_data(
                                master_contacts[email], contact, event_id
                            )
                        else:
                            master_contacts[email] = contact
            
                processed_snapshots.add(str(snapshot_path))
                
            except Exception as e:
                self.logger.error(f"Error processing snapshot {snapshot_path}: {str(e)}")
                continue
        
        # Save master file and update history
        self.processor._save_master_vcf(master_contacts)
        self.history['processed_snapshots'] = list(processed_snapshots)
        self._save_history()

    def _load_history(self):
        """Load contact processing history"""
        history_file = Path(self.snapshot_dir) / 'contact_history.json'
        if history_file.exists():
            try:
                return json.loads(history_file.read_text())
            except json.JSONDecodeError:
                self.logger.warning("Invalid history file, creating new one")
        
        # Initialize with correct structure
        return {
            'processed_files': [],
            'processed_snapshots': [],
            'contacts': {},  # For tracking contact history
            'last_update': None
        }

    def _update_history(self, filename: str, snapshot_path: str = None):
        """Update contact processing history"""
        if filename not in self.history['processed_files']:
            self.history['processed_files'].append(filename)
        if snapshot_path and snapshot_path not in self.history['processed_snapshots']:
            self.history['processed_snapshots'].append(str(snapshot_path))
        self.history['last_update'] = datetime.now().isoformat()
        self._save_history()

    def _save_history(self):
        """Save contact processing history"""
        history_file = Path(self.snapshot_dir) / 'contact_history.json'
        history_file.write_text(json.dumps(self.history, indent=2))

def load_config() -> Dict:
    """
    Load configuration from YAML file
    Returns:
        Dict: Configuration dictionary
    """
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def identify_event_type(filename: str, config: Dict) -> Optional[Dict]:
    """
    Match filename against known event identifiers
    
    Args:
        filename (str): Input filename
        config (Dict): Loaded configuration
    
    Returns:
        Optional[Dict]: Event type configuration if found, None if not matched
    
    Example:
        >>> config = load_config()
        >>> identify_event_type("Wine Yard The Gathering Guests Jan 19 2025.csv", config)
        {'name': 'Wine Yard', 'code': 'WY', ...}
    """
    # Remove ignored words
    cleaned_name = filename.lower()
    for word in config['event_config']['filename_parsing']['ignore_words']:
        cleaned_name = cleaned_name.replace(word.lower(), '')
    
    # Check each event type's identifiers
    for event_type, details in config['event_config']['types'].items():
        for identifier in details['identifiers']:
            if identifier.lower() in cleaned_name:
                return details
    
    return None

def extract_date(filename: str, config: Dict) -> Optional[datetime]:
    """
    Extract and parse date from filename using configured patterns
    
    Args:
        filename (str): Input filename
        config (Dict): Loaded configuration
    
    Returns:
        Optional[datetime]: Parsed date if found, None if no match
    
    Example:
        >>> config = load_config()
        >>> extract_date("Wine Yard The Gathering Guests Jan 19 2025.csv", config)
        datetime.datetime(2025, 1, 19)
    """
    for date_pattern in config['event_config']['filename_parsing']['date_patterns']:
        pattern = date_pattern['pattern']
        date_format = date_pattern['format']
        
        match = re.search(pattern, filename)
        if match:
            date_str = match.group(0)
            try:
                return datetime.strptime(date_str, date_format)
            except ValueError:
                continue
    
    return None

def generate_event_code(event_type: Dict, date: datetime, config: Dict) -> str:
    """
    Generate standardized event code
    
    Args:
        event_type (Dict): Event type configuration
        date (datetime): Event date
        config (Dict): Loaded configuration
    
    Returns:
        str: Formatted event code (e.g., "WY-2025-01-19")
    
    Example:
        >>> event_type = {'code': 'WY', ...}
        >>> date = datetime(2025, 1, 19)
        >>> generate_event_code(event_type, date, config)
        'WY-2025-01-19'
    """
    date_str = date.strftime(config['event_config']['output_format']['date_format'])
    return config['event_config']['output_format']['event_code'].format(
        code=event_type['code'],
        date=date_str
    )

def parse_event_filename(filename: str, config: Dict) -> Tuple[Optional[str], Optional[datetime]]:
    """
    Parse filename to extract event code and date
    
    Args:
        filename (str): Input filename
        config (Dict): Loaded configuration
    
    Returns:
        Tuple[Optional[str], Optional[datetime]]: (event_code, event_date)
        Returns (None, None) if parsing fails
    
    Example:
        >>> config = load_config()
        >>> parse_event_filename("Wine Yard The Gathering Guests Jan 19 2025.csv", config)
        ('WY-2025-01-19', datetime.datetime(2025, 1, 19))
    """
    event_type = identify_event_type(filename, config)
    if not event_type:
        print(f"Warning: Could not identify event type from filename: {filename}")
        return None, None
    
    date = extract_date(filename, config)
    if not date:
        print(f"Warning: Could not extract date from filename: {filename}")
        return None, None
    
    event_code = generate_event_code(event_type, date, config)
    return event_code, date

def normalize_column_name(column):
    # Normalize column names to remove special characters or replace them with simpler ones
    normalized = column.strip()  # Remove leading and trailing spaces
    normalized = normalized.replace('🧐', 'help_with')  # Replace emoji with text
    normalized = normalized.replace('💻', 'company')  # Replace emoji with text
    normalized = normalized.replace('🫶', 'joy')  # Replace emoji with text
    normalized = normalized.replace('🔗', 'linkedin')  # LinkedIn
    normalized = normalized.replace('🚀', 'master_plan')  # Replace emoji with text
    normalized = normalized.replace('🏆', 'impressive_person')  # Replace emoji with text
    return normalized

def ensure_directory_exists(directory):
    """Ensure the specified directory exists, create if it doesn't"""
    if not os.path.exists(directory):
        os.makedirs(directory)

def format_structured_notes(normalized_row: Dict, event_code: str, config: Dict) -> str:
    """
    Format contact notes in a structured way based on categories
    
    Returns formatted notes string with sections:
    === EVENTS ===
    WY-2025-01-19
    
    === PROFESSIONAL ===
    COMPANY: Example Corp
    
    === NEEDS ===
    HELP WITH: Fundraising
    """
    sections = []
    
    # Events Section
    sections.append("=== EVENTS ===")
    sections.append(event_code)
    
    # Get sections from config and sort by priority
    for section in sorted(config['event_config']['notes_format']['sections'], 
                         key=lambda x: x['priority']):
        section_name = section['name']
        if section_name == "EVENTS":
            continue  # Already handled
            
        section_content = []
        
        # Get questions for this category from config
        category = config['question_categories'].get(section_name.lower(), {})
        if category and 'questions' in category:
            for q_key, q_config in category['questions'].items():
                # Find matching answer in normalized_row
                for pattern in q_config['patterns']:
                    if answer := next((v for k, v in normalized_row.items() 
                                     if pattern.lower() in k.lower()), None):
                        section_content.append(f"{q_config['note_prefix']}: {answer}")
                        break
        
        if section_content:
            sections.append(f"\n=== {section_name} ===")
            sections.extend(section_content)
    
    return "\n".join(sections)

def merge_contact_data(existing_data: Dict, new_data: Dict, event_code: str, config: Dict) -> Dict:
    """
    Merge new contact data with existing data based on configuration rules
    """
    merged = existing_data.copy()
    
    # Get merge strategy from config
    merge_strategy = config['merge_strategy']
    
    for field, strategy in merge_strategy['fields'].items():
        if field == 'notes':
            # Append new event to events section
            existing_notes = merged.get('notes', '')
            if "=== EVENTS ===" in existing_notes:
                # Add new event to existing events section
                events_section = existing_notes.split("=== PROFESSIONAL ===")[0]
                rest_of_notes = existing_notes[len(events_section):]
                merged['notes'] = f"{events_section}{event_code}\n{rest_of_notes}"
            else:
                # Create new structured notes
                merged['notes'] = format_structured_notes(new_data, event_code, config)
        
        elif strategy == 'keep_latest':
            if field in new_data:
                merged[field] = new_data[field]
        
        elif strategy == 'keep_original':
            if field not in merged and field in new_data:
                merged[field] = new_data[field]
    
    return merged

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Process CSV contact files to VCF format'
    )
    parser.add_argument(
        'file',
        help='CSV file to process'
    )
    parser.add_argument(
        '--config',
        default='question_config.yaml',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    args = parser.parse_args()
    
    # Configure logging based on verbosity
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    logger.info("Starting contact converter")
    
    try:
        logger.info(f"Processing file: {args.file}")
        manager = ContactManager(args.config)
        manager.process_new_csv(args.file)
        logger.info(f"Successfully processed {args.file}")
        
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}", exc_info=args.verbose)
        sys.exit(1)
    
    logger.info("Contact converter completed successfully")

if __name__ == "__main__":
    main()
