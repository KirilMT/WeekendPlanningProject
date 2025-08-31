import re
import subprocess
import json
from itertools import groupby

def get_existing_issues(repo):
    """Fetch all existing issue titles from the GitHub repository."""
    try:
        result = subprocess.run(
            ['gh', 'issue', 'list', '--repo', repo, '--limit', '1000', '--json', 'title', '--jq', '.[] | .title'],
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
        '--body-file', '-',
        '--label', 'P2-Medium' # Default priority
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

def get_all_issues_with_details(repo):
    """Fetch all issues with details from the GitHub repository."""
    try:
        result = subprocess.run(
            ['gh', 'issue', 'list', '--repo', repo, '--limit', '1000', '--json', 'number,title,body,labels'],
            capture_output=True, text=True, check=True
        )
        return json.loads(result.stdout)
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error fetching issues with details: {e}")
        return None

def generate_issues_md(issues):
    """Generate the content for issues.md from a list of issues."""
    priority_map = {"P1-High": 1, "P2-Medium": 2, "P3-Low": 3}
    
    def get_priority_key(issue):
        for label in issue['labels']:
            if label['name'] in priority_map:
                return priority_map[label['name']]
        return 4

    issues.sort(key=get_priority_key)

    md_content = "# Project Issues\n\n"
    
    def get_priority_label(issue):
        for label in issue['labels']:
            if label['name'] in priority_map:
                return label['name']
        return "No Priority"

    issue_number = 1
    for priority_label, group in groupby(issues, key=get_priority_label):
        md_content += f"## {priority_label}\n\n"
        for issue in group:
            md_content += f"{issue_number}. ### {issue['title']} (#{issue['number']})\n"
            # The body from github has \r\n, need to replace them
            body = issue['body'].replace('\r\n', '\n')
            md_content += f"{body}\n\n"
            issue_number += 1
            
    return md_content

def main():
    """Main function to find new tasks, create them as GitHub issues, and update issues.md."""
    repo = "KirilMT/WeekendPlanningProject"
    roadmap_file = "ROADMAP.md"
    issues_md_file = "issues.md"

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

    if new_tasks:
        print(f"\nFound {len(new_tasks)} new tasks to create as issues.")
        for task in new_tasks:
            create_issue(task, repo)
    else:
        print("\n✅ All tasks in ROADMAP.md already exist as GitHub issues.")

    print("\nUpdating issues.md...")
    all_issues = get_all_issues_with_details(repo)
    if all_issues:
        md_content = generate_issues_md(all_issues)
        with open(issues_md_file, 'w', encoding='utf-8') as f:
            f.write(md_content)
        print(f"Successfully updated {issues_md_file}.")
    else:
        print("Could not fetch issues to update issues.md.")

if __name__ == "__main__":
    main()
