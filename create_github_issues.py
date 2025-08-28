import re
import subprocess

def get_existing_issues(repo):
    """Fetch all existing issue titles from the GitHub repository."""
    try:
        result = subprocess.run(
            ['gh', 'issue', 'list', '--repo', repo, '--limit', '1000', '--json', 'title', '--jq', '.[].title'],
            capture_output=True, text=True, check=True
        )
        return set(result.stdout.strip().split('\n'))
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Error fetching issues: {e}")
        print("Please ensure the GitHub CLI ('gh') is installed and you are authenticated ('gh auth login').")
        return None

def parse_roadmap(filepath):
    """Parse the ROADMAP.md file to extract categories and tasks."""
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    tasks = []
    current_category = ""
    for line in lines:
        category_match = re.match(r'^####\s+(.*)', line)
        task_match = re.match(r'^\s*-\s*\*\*(.*?)\*\*.*', line)
        sub_task_match = re.match(r'^\s+-\s+(.*)', line)

        if category_match:
            current_category = category_match.group(1).strip()
        elif task_match:
            title = task_match.group(1).strip()
            tasks.append({"title": title, "category": current_category, "body": ""})
        elif sub_task_match and tasks:
            # Append sub-tasks to the body of the last main task
            if not tasks[-1]["body"]:
                tasks[-1]["body"] = "### Sub-tasks:\n"
            tasks[-1]["body"] += f"- {sub_task_match.group(1).strip()}\n"

    return tasks

def create_issue(task, repo):
    """Create a GitHub issue for a given task."""
    title = task['title']
    category = task['category']
    body = f"**Category:** `{category}`\n\n{task.get('body', '')}"
    command = [
        'gh', 'issue', 'create',
        '--repo', repo,
        '--title', title,
        '--body-file', '-'  # Read body from stdin
    ]
    try:
        print(f"Creating issue: '{title}'...")
        result = subprocess.run(
            command, input=body, capture_output=True, text=True, check=True, encoding='utf-8'
        )
        print(f"Successfully created issue: {result.stdout.strip()}")
    except subprocess.CalledProcessError as e:
        print(f"Error creating issue '{title}':")
        print(e.stderr)
    except FileNotFoundError:
        print("Error: 'gh' command not found. Please ensure the GitHub CLI is installed.")


def main():
    """Main function to find new tasks and create them as GitHub issues."""
    repo = "KirilMT/WeekendPlanningProject"
    roadmap_file = "ROADMAP.md"

    print("Fetching existing issues from the repository...")
    existing_issues = get_existing_issues(repo)

    if existing_issues is None:
        return

    print(f"Found {len(existing_issues)} existing issues.")

    print("\nParsing ROADMAP.md to find new tasks...")
    tasks_to_create = parse_roadmap(roadmap_file)

    new_tasks = []
    for task in tasks_to_create:
        if task['title'] not in existing_issues:
            new_tasks.append(task)

    if not new_tasks:
        print("\n✅ All tasks in ROADMAP.md already exist as GitHub issues.")
        return

    print(f"\nFound {len(new_tasks)} new tasks to create as issues.")
    for task in new_tasks:
        create_issue(task, repo)

if __name__ == "__main__":
    main()
