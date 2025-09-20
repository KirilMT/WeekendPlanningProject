# How to Contribute

We'd love to accept your patches and contributions to this project. There are just a few small guidelines you need to follow.

## Community Guidelines

### Our Pledge

We, as members, contributors, and leaders, pledge to make participation in our community a harassment-free experience for everyone, regardless of age, body size, visible or invisible disability, ethnicity, sex characteristics, gender identity and expression, level of experience, education, socio-economic status, nationality, personal appearance, race, religion, or sexual identity and orientation.

We pledge to act and interact in ways that contribute to an open, welcoming, diverse, inclusive, and healthy community.

### Our Standards

Examples of behavior that contributes to a positive environment for our community include:

*   Demonstrating empathy and kindness toward other people
*   Being respectful of differing opinions, viewpoints, and experiences
*   Giving and gracefully accepting constructive feedback
*   Accepting responsibility and apologizing to those affected by our mistakes, and learning from the experience
*   Focusing on what is best not just for us as individuals, but for the overall community

Examples of unacceptable behavior include:

*   The use of sexualized language or imagery, and sexual attention or advances of any kind
*   Trolling, insulting or derogatory comments, and personal or political attacks
*   Public or private harassment
*   Publishing others' private information, such as a physical or email address, without their explicit permission
*   Other conduct which could reasonably be considered inappropriate in a professional setting

### Enforcement Responsibilities

Community leaders are responsible for clarifying and enforcing our standards and will take appropriate and fair corrective action in response to any behavior that they deem inappropriate, threatening, offensive, or harmful.

Community leaders have the right and responsibility to remove, edit, or reject comments, commits, code, wiki edits, issues, and other contributions that are not aligned to this Code of Conduct, and will communicate reasons for moderation decisions when appropriate.

### Scope

This Code of Conduct applies within all community spaces, and also applies when an individual is officially representing the community in public spaces. Examples of representing our community include using an official e-mail address, posting via an official social media account, or acting as an appointed representative at an online or offline event.

### Enforcement

Instances of abusive, harassing, or otherwise unacceptable behavior may be reported to the project team. All complaints will be reviewed and investigated promptly and fairly.

All community leaders are obligated to respect the privacy and security of the reporter of any incident.

---
The section below is specific to the WeekendPlanningProject project. It explains how we work, how we use GitHub, and what contributors can expect when engaging with this repository.
---

## Contribution Process

### Before contributing code

Before doing any significant work, open an issue to propose your idea and ensure alignment. You can either [file a new issue](https://github.com/YourOrganization/WeekendPlanningProject/issues/new/choose), or comment on an [existing one](https://github.com/YourOrganization/WeekendPlanningProject/issues). A pull request (PR) that does not go through this coordination process may be closed to avoid wasted effort.

## Checking the issue tracker

We use GitHub issues to track tasks, bugs, and discussions. All changes, except trivial ones, should start with a GitHub issue. This process gives everyone a chance to validate the design, helps prevent duplication of effort, and ensures that the idea fits inside the goals for the language and tools. It also checks that the design is sound before code is written; the code review tool is not the place for high-level discussions.

Always include a clear description in the body of the issue. The description should provide enough context for any team member to understand the problem or request without needing to contact you directly for clarification.

## Sending a pull request

All code changes must go through a pull request. First-time contributors should review [GitHub flow](https://docs.github.com/en/get-started/using-github/github-flow).

Before sending a pull request, it should include tests if there are logic changes, copyright headers in every file, and a commit message following the conventions in "Commit messages" section below.

A pull request can be opened from a branch within the repository or from a fork. External contributors are only able to open pull requests from forks, but team members with write access can choose to open a pull request from a repository branch.

If you open a pull request from a personal fork, you should allow repository maintainers to make edits to your fork by turning on "Allow edits from maintainers". Please see [creating a pull request from a fork](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request-from-a-fork) in the official GitHub documentation for details.

## Commit messages

Commit messages for WeekendPlanningProject follow the conventions below. Here is an example:

'''
feat(internal/WeekendPlanningProject): add version subcommand

A version subcommand is added to WeekendPlanningProject, which prints the current version of the tool. The version follows the versioning conventions described at https://go.dev/ref/mod#versions.

Resolves #12345
'''

### First line

The first line of the change description is a short one-line summary of the change, following the structure `(): `:

#### type

A structural element defined by the conventions at https://www.conventionalcommits.org/en/v1.0.0/#summary.

#### package

The name of the package affected by the change, and should be provided in parentheses before the colon.

#### description

A short one-line summary of the change, that should be written to complete the sentence "This change modifies WeekendPlanningProject to ..." That means it does not start with a capital letter, is not a complete sentence, and actually summarizes the result of the change. Note that the verb after the colon is lowercase, and there is no trailing period

The first line should be kept as short as possible (many git viewing tools prefer under ~76 characters). Follow the first line by a blank line.

### Main content

The rest of the commit message should provide context for the change and explain what it does. Write in complete sentences with correct punctuation. Don't use HTML, Markdown, or any other markup language.

Add any relevant information, such as benchmark data if the change affects performance. The benchstat tool is conventionally used to format benchmark data for change descriptions.

### Referencing issues

To automatically close an issue when a pull request (PR) is merged on GitHub, you need to include a specific keyword followed by the issue number in the PR's description or a commit message. For example, `Resolves #12345`.

When this change is eventually applied, the issue tracker will automatically mark the issue as fixed. You can use keywords like `Fixes`, `Closes`, or `Resolves`.

If the change is a partial step towards the resolution of the issue, write "For #12345" instead. This will leave a comment in the issue linking back to the pull request, but it will not close the issue when the change is applied.

## The review process

This section explains the review process in detail and how to approach reviews after a pull request has been sent for review.

### Getting a code review

Before creating a pull request, make sure that your commit message follows the suggested format. Otherwise, it can be common for the pull request to be sent back with that request without review.

After creating a pull request, request a specific reviewer if relevant, or leave it for the default group.

### Merging a pull request

Pull request titles and descriptions must follow the [commit messages](#commit-messages) conventions. This enables approvers to review the final commit message.

Once the pull request has been approved and all checks have passed, click the [Squash and Merge](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/about-pull-request-merges#squash-and-merge-your-commits) button. The resulting commit message will be based on the pull request's title and description.

### Reverting a pull request

If a merged pull request needs to be undone, for reasons such as breaking the build, the standard process is to [revert it through the GitHub interface](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/reverting-a-pull-request). To revert a pull request:

1.  Navigate to the merged pull request on GitHub.
2.  Click the **Revert** button. This action automatically creates a new branch and a pull request containing the revert commit.
3.  Edit the pull request title and description to comply with the [commit message guidelines](#commit-messages).
4.  The newly created revert pull request should be reviewed and merged following the same process as any other pull request.

Using the GitHub "Revert" button is the preferred method over manually creating a revert commit using `git revert`.

### Keeping the pull request dashboard clean

We aim to keep https://github.com/YourOrganization/WeekendPlanningProject/pulls clean so that we can quickly notice and review incoming changes that require attention. Given that goal, please do not open a pull request unless you are ready for a code review. Draft pull requests and ones without author activity for more than one business day may be closed (they can always be reopened later). If you're still working on something, continue iterating on your branch without creating a pull request until it’s ready for review.

### Addressing code review comments

Creating additional commits to address reviewer feedback is generally preferred over amending and force-pushing. This makes it easier for reviewers to see what has changed since their last review. Pull requests are always squashed and merged. Before merging, please review and edit the resulting commit message to ensure it clearly describes the change.

After pushing, [click the button](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/requesting-a-pull-request-review#requesting-reviews-from-collaborators-and-organization-members) to ask a reviewer to re-request your review.

## Leaving a TODO

When adding a TODO to the codebase, always include a link to an issue, no matter how small the task. Use the format:

'''
// TODO(https://github.com/YourOrganization/WeekendPlanningProject/issues/): explain what needs to be done
'''

This helps provide context for future readers and keeps the TODO relevant and actionable as the project evolves.
