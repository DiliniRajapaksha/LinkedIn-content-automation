# LinkedIn Notion Auto-Poster

Automate your LinkedIn content posting using Notion as a content management system. Schedule your posts in Notion, and this script will automatically publish them to LinkedIn at the right time.

## Features

- 📅 Schedule posts using Notion's built-in date fields
- 📝 Support for text-only and image posts
- 🔄 Automatic status updates in Notion after posting
- 🔒 Secure credential management
- 🤖 Ready for GitHub Actions deployment

## Prerequisites

- Python 3.7 or higher
- A Notion account with an integration
- A LinkedIn Developer account with an application
- A GitHub account (for automated deployment)

## Setup

### 1. Notion Setup

1. Duplicate this Notion Database: https://animated-volleyball-052.notion.site/26c0ceff95eb8048ad32e4a8588f44e3?v=26c0ceff95eb81d4a2aa000c99d0292b

2. Create a Notion integration:
   - Go to [https://www.notion.so/my-integrations](https://www.notion.so/my-integrations)
   - Create a new integration
   - Save the API token
   - Share your database with the integration

### 2. LinkedIn Setup

1. Create a LinkedIn Developer Application:
   - Go to [LinkedIn Developers](https://www.linkedin.com/developers/apps)
   - Create a new app
   - Request the necessary permissions for posting
   - Get your access token and person ID

### 3. Local Development Setup

1. Clone this repository:
   ```bash
   git clone https://github.com/DiliniRajapaksha/LinkedIn-content-automation.git
   cd LinkedInContent
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

### 4. GitHub Actions Setup

1. Fork this repository

2. Add repository secrets:
   - `NOTION_API_TOKEN`
   - `NOTION_DATABASE_ID`
   - `LINKEDIN_ACCESS_TOKEN`
   - `LINKEDIN_PERSON_ID`

The GitHub Action will run daily at 20:00 UTC (6:00 AM AEST next day).

## Usage

### Local Development

Run once:
```bash
python LinkedIn_publisher_v2.py
```

### Notion Database Usage

1. Create a new page in your Notion database
2. Set the Status to "Scheduled"
4. Set the Schedule Date
5. Write your post content in the LinkedIn Post field
6. (Optional) Add images

The script will automatically:
1. Find posts scheduled for today
2. Publish them to LinkedIn
3. Update their status to "Posted"
4. Add the publication date

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `NOTION_API_TOKEN` | Your Notion integration token | Yes |
| `NOTION_DATABASE_ID` | Your Notion database ID | Yes |
| `LINKEDIN_ACCESS_TOKEN` | LinkedIn API access token | Yes |
| `LINKEDIN_PERSON_ID` | LinkedIn person URN | Yes |
| `TIMEZONE` | Your timezone (default: Australia/Brisbane) | No |

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Thanks to Notion for their excellent API
- Thanks to LinkedIn for their developer platform
