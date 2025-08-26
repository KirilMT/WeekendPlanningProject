from dotenv import load_dotenv
import os

# Load environment variables from .env file before anything else
load_dotenv()

from wkndPlanning.app import app

if __name__ == '__main__':
    # The debug mode for the Flask server is now controlled by the DEBUG_MODE
    # environment variable loaded from the .env file via the Config object.
    # The 'debug' parameter for app.run() can be set directly from the config.
    is_debug_mode = app.config.get('DEBUG_MODE', False)

    # The reloader should be used in debug mode for a better development experience.
    use_reloader = is_debug_mode

    app.run(host='127.0.0.1', port=5000, debug=is_debug_mode, use_reloader=use_reloader)
