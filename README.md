# Medicine Donation Eligibility & NGO Matching Website

A production-ready Streamlit web application that helps donors check if their medicines are eligible for donation and matches them with appropriate NGOs. The application includes a comprehensive admin panel, chatbot with voice input, and speech-to-text capabilities.

## Features

- **Donation Eligibility Check**: Determines if a medicine can be donated based on expiry dates or shelf life information (180-day threshold)
- **NGO Matching**: Finds and matches eligible donations with NGOs based on location
- **Donation Management**: Records and tracks donations with status updates
- **Assistant Chatbot**: Text and voice-based assistant with:
  - Speech-to-text transcription (Whisper-tiny) via Hugging Face API or local models
  - Intent classification (DistilBERT) for understanding user queries
  - Rule-based and AI-powered response generation
- **Admin Panel**: Full CRUD operations for:
  - **Donations**: View, search, filter (case-insensitive), export, and delete donations
  - **NGOs**: Add, edit, view, and export NGO information
  - **Shelf Life**: Add and manage medicine shelf life entries
  - **Statistics**: View database summary statistics

## Installation

1. **Install Python dependencies:**
```bash
python -m pip install -r requirements.txt
```

2. **Initialize the database:**
```bash
python db_init.py
```

This will create the SQLite database (`meddonation.db`) with the necessary tables and sample data.

## Running the Application

Start the Streamlit application:

```bash
python -m streamlit run app.py
```

Or use the combined command:

```bash
python db_init.py && python -m streamlit run app.py
```

The application will open in your default web browser, typically at `http://localhost:8501`.

## Hugging Face API Configuration (Optional)

To use the Hugging Face Inference API for enhanced ASR, classification, and chat generation:

1. **Get a Hugging Face API token:**
   - Sign up at https://huggingface.co
   - Go to Settings → Access Tokens
   - Create a new token with read permissions

2. **Set environment variables:**
   ```bash
   # Windows (PowerShell)
   $env:HF_API_TOKEN="your_token_here"
   $env:USE_HF_API="1"
   
   # Linux/Mac
   export HF_API_TOKEN="your_token_here"
   export USE_HF_API="1"
   ```

3. **Or create a `.env` file** (not committed to git):
   ```
   HF_API_TOKEN=your_token_here
   USE_HF_API=1
   ```

**Note:** If HF API is not configured, the application will:
- Use rule-based responses for chat
- Skip ASR transcription (user can still use text input)
- Use simple rule-based intent classification

## Local Model Installation (Alternative to HF API)

If you prefer to use local models instead of the HF Inference API, uncomment these lines in `requirements.txt`:

```
transformers
torch
soundfile
```

Then install:
```bash
python -m pip install -r requirements.txt
```

**Warning:** Local models require significant disk space (~2-3 GB) and may be slower than the API.

## Project Structure

- `db_init.py`: Database initialization script with idempotent creation
- `utils.py`: Business logic functions for eligibility checking and NGO matching
- `admin_utils.py`: Admin CRUD operations returning pandas DataFrames
- `chat_utils.py`: Chat utilities with ASR, intent classification, and response generation
- `app.py`: Main Streamlit application with donation form, chatbot, and admin panel
- `tests/test_admin_utils.py`: Pytest tests for admin functions
- `meddonation.db`: SQLite database (created after running db_init.py)
- `app.log`: Application log file

## Admin Features

### Donations Management
- View all donations with filters (donor name, medicine name, city) - case-insensitive substring match
- Export donations to CSV (UTF-8 encoded)
- Delete donations (with confirmation checkbox required)

### NGOs Management
- View all NGOs
- Add new NGOs with name, city, contact, and accepted medicine types
- Edit existing NGO information
- Export NGOs to CSV

### Shelf Life Management
- View all shelf life entries
- Add new medicine shelf life entries
- Export shelf life data to CSV

### Statistics
- View total donations count
- View total NGOs count
- View total shelf life entries count

## Database Schema

### Tables

**shelf_life**
- `id`: Primary key
- `medicine_name`: Unique medicine name
- `shelf_months`: Shelf life in months
- `notes`: Additional notes

**ngos**
- `id`: Primary key
- `name`: NGO name
- `city`: City location
- `contact`: Contact information
- `accepts`: Types of medicines accepted

**donations**
- `id`: Primary key
- `donor_name`: Donor's name
- `medicine_name`: Medicine name
- `batch_date`: Manufacture/batch date
- `expiry_date`: Expiry date (optional)
- `status`: Donation status (default: 'pledged')
- `matched_ngo_id`: Foreign key to ngos table

## Testing

Run the test suite:

```bash
python -m pytest tests/
```

Tests will safely skip if the database is not found.

## Project Reference

This project is based on specifications provided in the local file:
`/mnt/data/mini_projectruchi[1]2 (1).pptx`

**Important:** The methodology content from the specification file is **not displayed** in the application UI. Only a reference path is provided for instructors. The app UI intentionally does not display the methodology text.

## Security Features

- All database operations use parameterized queries to prevent SQL injection
- Delete operations require explicit confirmation via checkbox
- Error logging to `app.log` file
- User-friendly error messages (no tracebacks displayed to users)
- All CSV exports use UTF-8 encoding

## Logging

All database operations and errors are logged to `app.log` for debugging and monitoring purposes. Check this file if you encounter any issues.

## Assumptions

This implementation assumes:
- SQLite database is sufficient for the application scale
- Users have basic familiarity with web forms
- Audio files for transcription are in common formats (WAV, MP3, M4A, OGG)
- Hugging Face API is optional and the application works with rule-based fallbacks
- The 180-day threshold for donation eligibility is appropriate for the use case
- All date inputs are in YYYY-MM-DD format or use the date picker widget

## License

This project is for educational purposes.
