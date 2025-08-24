let technicianGroups = {};
let uploadedFile = null;
let repTasks = [];
let currentRepTaskIndex = 0;
let repAssignments = [];
let presentTechnicians = [];
let eligibleTechnicians = {};
let filename = '';
let sessionId = '';
let additionalTaskCounter = 0;
let availableSkills = []; // Store available skills for task creation

// Generate a simple session ID
function generateSessionId() {
    return Math.random().toString(36).substring(2, 15);
}

// Initialize CSRF token from meta tag
function getCSRFToken() {
    const token = document.querySelector('meta[name="csrf-token"]');
    return token ? token.getAttribute('content') : '';
}

// Fetch the grouped technicians from the server
console.log('INDEX.HTML: Fetching technician groups...');
fetch('/api/technicians')
    .then(response => {
        console.log('INDEX.HTML: Technicians response status:', response.status);
        return response.json();
    })
    .then(data => {
        console.log('INDEX.HTML: Technician groups received:', data);
        technicianGroups = data;
    })
    .catch(error => {
        console.error('INDEX.HTML: Error fetching technicians:', error);
        showMessage('Error fetching technicians list. Please refresh the page.', 'error');
    });

// Fetch available skills for task creation
function loadAvailableSkills() {
    fetch('/api/technologies')
        .then(response => response.json())
        .then(data => {
            availableSkills = data;
            populateSkillsSelect();
        })
        .catch(error => {
            console.error('Error fetching skills:', error);
        });
}

function populateSkillsSelect() {
    const skillsSelect = document.getElementById('requiredSkillsSelect');
    if (skillsSelect && availableSkills.length > 0) {
        skillsSelect.innerHTML = '';
        availableSkills.forEach(skill => {
            const option = document.createElement('option');
            option.value = skill.id;
            option.textContent = skill.name;
            skillsSelect.appendChild(option);
        });
    }
}

function populateTechnicianGroups() {
    console.log('INDEX.HTML: Populating technician groups...');
    if (!Object.keys(technicianGroups).length) {
        console.error('INDEX.HTML: No technician groups available for populateTechnicianGroups.');
        showMessage('No technicians available. Please check server configuration.', 'error');
        return;
    }
    const groupsContainer = document.getElementById('technicianGroups');
    if (!groupsContainer) {
        console.error('INDEX.HTML: technicianGroups container not found!');
        return;
    }

    groupsContainer.innerHTML = '';

    let satelliteIndex = 1;
    for (const [groupName, technicians] of Object.entries(technicianGroups)) {
        const groupDiv = document.createElement('div');
        groupDiv.className = `group ${groupName.toLowerCase()} satellite-${satelliteIndex}`;

        const groupTitle = document.createElement('h3');
        groupTitle.textContent = groupName;
        groupDiv.appendChild(groupTitle);

        const buttonsDiv = document.createElement('div');
        buttonsDiv.className = 'technician-buttons';

        technicians.forEach(tech => {
            const button = document.createElement('button');
            button.className = 'technician-button';
            button.textContent = tech;
            button.type = 'button';
            button.dataset.technician = tech;
            button.addEventListener('click', function () {
                this.classList.toggle('absent');
            });
            buttonsDiv.appendChild(button);
        });

        groupDiv.appendChild(buttonsDiv);
        groupsContainer.appendChild(groupDiv);

        // Increment satellite index, reset to 1 if we exceed 10 colors
        satelliteIndex = satelliteIndex >= 10 ? 1 : satelliteIndex + 1;
    }
    console.log('INDEX.HTML: Technician groups populated.');
}

function showMessage(text, type) {
    const messageDiv = document.getElementById('message');
    if (messageDiv) {
        messageDiv.style.display = 'block';
        messageDiv.className = `message-container ${type}`;
        messageDiv.textContent = text;
        messageDiv.scrollIntoView({behavior: 'smooth', block: 'center'});
    } else {
        console.error("INDEX.HTML: Message div not found!");
    }
}

function showModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'flex';
        modal.setAttribute('aria-hidden', 'false');

        // Remove focus from any previously focused element to prevent aria-hidden conflicts
        if (document.activeElement && document.activeElement.blur) {
            document.activeElement.blur();
        }

        // Focus the first focusable element in the modal after a brief delay
        setTimeout(() => {
            const firstFocusable = modal.querySelector('button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"]):not([disabled])');
            if (firstFocusable) {
                firstFocusable.focus();
            }
        }, 100);
    }
}

function hideModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        // Remove focus from any focused element inside the modal before hiding
        const focusedElement = modal.querySelector(':focus');
        if (focusedElement && focusedElement.blur) {
            focusedElement.blur();
        }

        // Hide the modal and set aria-hidden after focus is cleared
        setTimeout(() => {
            modal.style.display = 'none';
            modal.setAttribute('aria-hidden', 'true');
        }, 10);
    }
}

function showAbsentModal() {
    console.log('INDEX.HTML: Showing absent modal...');
    populateTechnicianGroups();
    showModal('absentModal');
}

function hideAbsentModal() {
    console.log('INDEX.HTML: Hiding absent modal...');
    hideModal('absentModal');
}

function showTaskAssignmentModal() {
    console.log('INDEX.HTML: showTaskAssignmentModal called. Current task index:', currentRepTaskIndex, 'Total tasks:', repTasks.length);
    if (currentRepTaskIndex < repTasks.length) {
        const task = repTasks[currentRepTaskIndex];
        console.log('INDEX.HTML: Current task for modal:', task);

        const taskInfoDiv = document.getElementById('taskInfo');
        if (taskInfoDiv) {
            taskInfoDiv.innerHTML = `
                <div class="task-details">
                    <h3>${task.name || task.scheduler_group_task || 'Unknown Task'}</h3>
                    <div class="task-meta">
                        <span class="task-type">${task.task_type || 'REP'}</span>
                        <span class="task-duration">${task.planned_worktime_min} min</span>
                        <span class="task-technicians">${task.mitarbeiter_pro_aufgabe} technicians needed</span>
                    </div>
                    ${task.ticket_mo ? `<p><strong>Ticket/MO:</strong> ${task.ticket_mo}</p>` : ''}
                    ${task.ticket_url ? `<p><strong>Link:</strong> <a href="${task.ticket_url}" target="_blank" rel="noopener">${task.ticket_url}</a></p>` : ''}
                    <p><strong>Progress:</strong> ${currentRepTaskIndex + 1} of ${repTasks.length}</p>
                    ${task.isAdditionalTask ? '<span class="additional-task-badge">Additional Task</span>' : ''}
                </div>
            `;
        } else {
            console.error("INDEX.HTML: taskInfo div not found!");
        }

        populateTaskTechnicians(task);
        showModal('taskAssignmentModal');
    } else {
        console.log('INDEX.HTML: All tasks processed, submitting final assignments...');
        submitFinalAssignments();
    }
}

function populateTaskTechnicians(task) {
    console.log('INDEX.HTML: populateTaskTechnicians called for task ID:', task.id, 'Task Details:', task);

    const techniciansContainer = document.querySelector('#availableTechnicians .technician-checkboxes');
    if (!techniciansContainer) {
        console.error("INDEX.HTML: technician checkboxes container not found!");
        return;
    }

    techniciansContainer.innerHTML = '';

    // Get eligible technicians for this task
    const taskEligibleTechnicians = eligibleTechnicians[task.id] || [];

    if (taskEligibleTechnicians.length === 0) {
        techniciansContainer.innerHTML = '<p class="no-technicians">No eligible technicians found for this task.</p>';
        return;
    }

    taskEligibleTechnicians.forEach(tech => {
        const techDiv = document.createElement('div');
        techDiv.className = 'technician-option';

        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.id = `tech_${tech.name}`;
        checkbox.value = tech.name;
        checkbox.name = 'selectedTechnicians';

        const label = document.createElement('label');
        label.htmlFor = checkbox.id;
        label.innerHTML = `
            <span class="tech-name">${tech.name}</span>
            <span class="tech-time">Available: ${tech.available_time}min</span>
        `;

        techDiv.appendChild(checkbox);
        techDiv.appendChild(label);
        techniciansContainer.appendChild(techDiv);
    });
}

function hideTaskAssignmentModal() {
    hideModal('taskAssignmentModal');
}

function showAdditionalTaskModal() {
    loadAvailableSkills(); // Load skills when opening the modal
    showModal('additionalTaskModal');
}

function hideAdditionalTaskModal() {
    hideModal('additionalTaskModal');
}

function submitFinalAssignments() {
    // NOW is the right time to hide button and disable file input
    // This happens after absent modal and all REP task assignments are done
    const submitBtn = document.querySelector('#uploadForm button[type="submit"]');
    if (submitBtn) {
        submitBtn.style.display = 'none';
    }
    disableFileInput();

    // Show progress bar now - during actual dashboard generation
    const progressInterval = showProgressBar();

    const formData = new FormData();
    formData.append('csrf_token', getCSRFToken());
    formData.append('present_technicians', JSON.stringify(presentTechnicians));
    formData.append('rep_assignments', JSON.stringify(repAssignments));
    formData.append('session_id', sessionId);
    formData.append('all_processed_tasks', JSON.stringify(repTasks));

    fetch('/generate_dashboard', {
        method: 'POST',
        body: formData
    })
    .then(response => {
        console.log('INDEX.HTML: /generate_dashboard response status:', response.status);
        return response.json();
    })
    .then(data => {
        console.log('INDEX.HTML: /generate_dashboard response data:', data);

        // Hide progress bar when dashboard generation is complete
        hideProgressBar(progressInterval);

        showMessage(data.message, data.message.includes('Error') ? 'error' : 'success');
        if (data.dashboard_url) {
            const openDashboardButton = document.getElementById('openDashboardButton');
            if (openDashboardButton) {
                openDashboardButton.onclick = () => window.open(data.dashboard_url, '_blank');
                openDashboardButton.style.display = 'inline-flex';
            }

            // Show the "Generate New Dashboard" button after successful generation
            showGenerateNewDashboardButton();
        }
    })
    .catch(error => {
        console.error('INDEX.HTML: Error in /generate_dashboard:', error);

        // Hide progress bar on error
        hideProgressBar(progressInterval);

        showMessage('Error generating dashboard. Please try again.', 'error');
    });
}

function setButtonLoading(button, isLoading) {
    if (!button) return;

    if (isLoading) {
        button.classList.add('loading');
        button.disabled = true;
        button.dataset.originalText = button.textContent;
        button.innerHTML = '<span class="btn-icon">⏳</span> Processing...';
    } else {
        button.classList.remove('loading');
        button.disabled = false;
        if (button.dataset.originalText) {
            button.innerHTML = `<span class="btn-icon">⚡</span> ${button.dataset.originalText.replace('⚡ ', '')}`;
        }
    }
}

function showProgressBar() {
    // Remove any existing progress container first
    const existingProgress = document.getElementById('progressContainer');
    if (existingProgress) {
        existingProgress.remove();
    }

    const progressContainer = document.createElement('div');
    progressContainer.id = 'progressContainer';
    progressContainer.className = 'progress-container';
    progressContainer.style.display = 'flex'; // Ensure it's visible
    progressContainer.innerHTML = `
        <div>
            <div class="progress-header">
                <h3>🚀 Generating Skill-Based Assignments</h3>
                <p>Please wait while we process your data...</p>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" id="progressFill"></div>
            </div>
            <div class="progress-steps">
                <div class="step active" id="step1">📊 Processing Excel Data</div>
                <div class="step" id="step2">👥 Analyzing Technician Skills</div>
                <div class="step" id="step3">⚙️ Matching Tasks to Skills</div>
                <div class="step" id="step4">📋 Generating Dashboard</div>
            </div>
        </div>
    `;

    document.body.appendChild(progressContainer);

    // Force reflow to ensure element is rendered
    progressContainer.offsetHeight;

    // Animate progress
    let progress = 0;
    const progressFill = document.getElementById('progressFill');
    const steps = ['step1', 'step2', 'step3', 'step4'];
    let currentStep = 0;

    const progressInterval = setInterval(() => {
        progress += Math.random() * 10 + 3; // Smaller, more realistic increments
        if (progress > 85) progress = 85; // Don't complete until actual completion

        progressFill.style.width = `${progress}%`;

        // Update active step and mark completed steps as green
        const newStep = Math.floor(progress / 22);
        if (newStep > currentStep && newStep < steps.length) {
            // Mark the current step as completed (green) before moving to next
            const currentStepEl = document.getElementById(steps[currentStep]);
            if (currentStepEl) {
                currentStepEl.classList.remove('active');
                currentStepEl.classList.add('completed');
            }

            // Set the new step as active
            const newStepEl = document.getElementById(steps[newStep]);
            if (newStepEl) {
                newStepEl.classList.add('active');
            }

            currentStep = newStep;
        }
    }, 800); // Slower updates for better visibility

    return progressInterval;
}

function hideProgressBar(progressInterval) {
    if (progressInterval) {
        clearInterval(progressInterval);
    }

    const progressContainer = document.getElementById('progressContainer');
    if (progressContainer) {
        // Complete the progress bar
        const progressFill = document.getElementById('progressFill');
        if (progressFill) {
            progressFill.style.width = '100%';
        }

        // Mark all steps as complete
        document.querySelectorAll('.step').forEach(step => {
            step.classList.remove('active');
            step.classList.add('completed');
        });

        // Remove after showing completion
        setTimeout(() => {
            progressContainer.remove();
        }, 1000);
    }
}

// Helper functions for UI updates
function updateFileDisplay(fileName) {
    const fileLabel = document.querySelector('.file-label');
    if (fileLabel) {
        fileLabel.innerHTML = `
            <span class="file-icon">✅</span>
            <span class="file-name">${fileName}</span>
        `;
        fileLabel.style.background = '#ecfdf5';
        fileLabel.style.borderColor = '#10b981';
        fileLabel.style.color = '#065f46';
    }
}

function disableFileInput() {
    const fileInput = document.getElementById('excelFile');
    const fileLabel = document.querySelector('.file-label');

    if (fileInput) {
        fileInput.disabled = true;
    }

    if (fileLabel) {
        fileLabel.style.pointerEvents = 'none';
        fileLabel.style.opacity = '0.6';
        fileLabel.style.cursor = 'not-allowed';
        fileLabel.style.background = '#f3f4f6';
        fileLabel.style.borderColor = '#d1d5db';
        fileLabel.style.color = '#9ca3af';
    }
}

function enableFileInput() {
    const fileInput = document.getElementById('excelFile');
    const fileLabel = document.querySelector('.file-label');

    if (fileInput) {
        fileInput.disabled = false;
        fileInput.value = ''; // Clear the file selection
    }

    if (fileLabel) {
        fileLabel.style.pointerEvents = 'auto';
        fileLabel.style.opacity = '1';
        fileLabel.style.cursor = 'pointer';
        fileLabel.style.background = '#f9fafb';
        fileLabel.style.borderColor = '#d1d5db';
        fileLabel.style.color = '#6b7280';
        fileLabel.innerHTML = `
            <span class="file-icon">📁</span>
            Choose Excel File
        `;
    }
}

function showGenerateNewDashboardButton() {
    const uploadSection = document.querySelector('.upload-section');
    if (uploadSection) {
        // Remove existing generate new button if it exists
        const existingButton = document.getElementById('generateNewDashboardBtn');
        if (existingButton) {
            existingButton.remove();
        }

        const generateNewBtn = document.createElement('button');
        generateNewBtn.id = 'generateNewDashboardBtn';
        generateNewBtn.className = 'btn btn-primary';
        generateNewBtn.innerHTML = '<span class="btn-icon">🔄</span> Generate New Dashboard';
        generateNewBtn.addEventListener('click', function() {
            resetToInitialState();
        });

        uploadSection.appendChild(generateNewBtn);
    }
}

function resetToInitialState() {
    // Reset all variables
    uploadedFile = null;
    repTasks = [];
    currentRepTaskIndex = 0;
    repAssignments = [];
    presentTechnicians = [];
    eligibleTechnicians = {};
    filename = '';
    additionalTaskCounter = 0;

    // Generate new session ID
    sessionId = generateSessionId();

    // Show the original submit button
    const submitBtn = document.querySelector('#uploadForm button[type="submit"]');
    if (submitBtn) {
        submitBtn.style.display = 'inline-flex';
        setButtonLoading(submitBtn, false);
    }

    // Re-enable file input
    enableFileInput();

    // Hide dashboard and generate new buttons
    const openDashboardButton = document.getElementById('openDashboardButton');
    const generateNewBtn = document.getElementById('generateNewDashboardBtn');

    if (openDashboardButton) {
        openDashboardButton.style.display = 'none';
    }

    if (generateNewBtn) {
        generateNewBtn.remove();
    }

    // Clear any messages
    const messageDiv = document.getElementById('message');
    if (messageDiv) {
        messageDiv.style.display = 'none';
        messageDiv.textContent = '';
    }
}

// Event Listeners
document.addEventListener('DOMContentLoaded', function() {
    // Initialize session ID
    sessionId = generateSessionId();

    // Upload form handler
    const uploadForm = document.getElementById('uploadForm');
    if (uploadForm) {
        uploadForm.addEventListener('submit', function(e) {
            e.preventDefault();
            console.log('INDEX.JS: Upload form submitted.');

            const fileInput = document.getElementById('excelFile');
            if (!fileInput || !fileInput.files[0]) {
                showMessage('Please select an Excel file.', 'error');
                return;
            }

            uploadedFile = fileInput.files[0];
            filename = uploadedFile.name;

            // Show selected file name
            updateFileDisplay(filename);

            const formData = new FormData();
            formData.append('csrf_token', getCSRFToken());
            formData.append('excelFile', uploadedFile);
            formData.append('session_id', sessionId);

            console.log('INDEX.JS: Sending initial upload request...');

            // Keep button visible and unchanged - no loading state

            fetch('/upload', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                console.log('INDEX.JS: Initial upload response status:', response.status);
                return response.json();
            })
            .then(data => {
                console.log('INDEX.JS: Initial upload response data:', data);

                if (data.error) {
                    showMessage(data.error, 'error');
                    return;
                }

                repTasks = data.rep_tasks || [];
                eligibleTechnicians = data.eligible_technicians || {};

                console.log('INDEX.JS: Initial upload successful, preparing for absent modal.');
                console.log('INDEX.JS: repTasks after initial upload:', repTasks);

                // Button stays visible and unchanged
                showAbsentModal();
            })
            .catch(error => {
                console.error('INDEX.JS: Error in initial upload:', error);
                showMessage('Upload failed. Please try again.', 'error');
            });
        });
    }

    // File input change handler to show selected file
    const fileInput = document.getElementById('excelFile');
    if (fileInput) {
        fileInput.addEventListener('change', function() {
            if (this.files && this.files[0]) {
                updateFileDisplay(this.files[0].name);
            }
        });
    }

    // Absent modal confirm button
    const confirmAbsentBtn = document.getElementById('confirmAbsent');
    if (confirmAbsentBtn) {
        confirmAbsentBtn.addEventListener('click', function() {
            console.log('INDEX.HTML: Confirm absent technicians clicked.');

            const absentButtons = document.querySelectorAll('.technician-button.absent');
            const absentTechnicians = Array.from(absentButtons).map(btn => btn.dataset.technician);

            console.log('INDEX.HTML: Absent technicians selected:', absentTechnicians);

            // Calculate present technicians
            const allTechnicians = [];
            Object.values(technicianGroups).forEach(group => {
                allTechnicians.push(...group);
            });
            presentTechnicians = allTechnicians.filter(tech => !absentTechnicians.includes(tech));

            console.log('INDEX.HTML: Present technicians:', presentTechnicians);

            const formData = new FormData();
            formData.append('csrf_token', getCSRFToken());
            formData.append('absentTechnicians', JSON.stringify(absentTechnicians));
            formData.append('filename', filename);
            formData.append('session_id', sessionId);

            console.log('INDEX.HTML: Sending PM processing request (after absent selection)...');

            fetch('/upload', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                console.log('INDEX.HTML: PM processing response status:', response.status);
                return response.json();
            })
            .then(data => {
                console.log('INDEX.HTML: PM processing response data:', data);

                if (data.error) {
                    showMessage(data.error, 'error');
                    return;
                }

                repTasks = data.rep_tasks || [];
                eligibleTechnicians = data.eligible_technicians || {};

                console.log('INDEX.HTML: repTasks after PM processing:', repTasks);
                console.log('INDEX.HTML: eligibleTechnicians for REP tasks after PM processing:', eligibleTechnicians);

                hideAbsentModal();

                if (repTasks.length > 0) {
                    currentRepTaskIndex = 0;
                    showTaskAssignmentModal();
                } else {
                    console.log('INDEX.HTML: No REP tasks found, generating dashboard directly...');
                    submitFinalAssignments();
                }
            })
            .catch(error => {
                console.error('INDEX.HTML: Error in PM processing:', error);
                showMessage('Processing failed. Please try again.', 'error');
            });
        });
    }

    // Task assignment modal buttons
    const validateAssignmentBtn = document.getElementById('validateAssignment');
    if (validateAssignmentBtn) {
        validateAssignmentBtn.addEventListener('click', function() {
            const selectedCheckboxes = document.querySelectorAll('#availableTechnicians input[type="checkbox"]:checked');
            const selectedTechnicians = Array.from(selectedCheckboxes).map(cb => cb.value);

            if (selectedTechnicians.length === 0) {
                showMessage('Please select at least one technician.', 'error');
                return;
            }

            const currentTask = repTasks[currentRepTaskIndex];
            repAssignments.push({
                task_id: currentTask.id,
                task_name: currentTask.name,
                assigned_technicians: selectedTechnicians
            });

            currentRepTaskIndex++;
            hideTaskAssignmentModal();
            showTaskAssignmentModal(); // Show next task or finish
        });
    }

    const skipTaskBtn = document.getElementById('skipTask');
    if (skipTaskBtn) {
        skipTaskBtn.addEventListener('click', function() {
            const currentTask = repTasks[currentRepTaskIndex];
            repAssignments.push({
                task_id: currentTask.id,
                task_name: currentTask.name,
                assigned_technicians: []
            });

            currentRepTaskIndex++;
            hideTaskAssignmentModal();
            showTaskAssignmentModal(); // Show next task or finish
        });
    }

    const addAdditionalTaskBtn = document.getElementById('addAdditionalTask');
    if (addAdditionalTaskBtn) {
        addAdditionalTaskBtn.addEventListener('click', function() {
            showAdditionalTaskModal();
        });
    }

    // Additional task form
    const additionalTaskForm = document.getElementById('additionalTaskForm');
    if (additionalTaskForm) {
        additionalTaskForm.addEventListener('submit', function(e) {
            e.preventDefault();

            const formData = new FormData(this);
            const taskData = {
                id: `additional_${++additionalTaskCounter}`,
                name: formData.get('taskName'),
                lines: formData.get('taskLines') || '',
                ticket_mo: formData.get('taskTicketMO') || '',
                ticket_url: formData.get('taskTicketURL') || '',
                planned_worktime_min: parseInt(formData.get('taskDuration')),
                mitarbeiter_pro_aufgabe: parseInt(formData.get('taskTechnicians')),
                quantity: parseInt(formData.get('taskQuantity')),
                task_type: formData.get('taskType'),
                required_skills: Array.from(formData.getAll('requiredSkills')),
                isAdditionalTask: true
            };

            repTasks.push(taskData);
            hideAdditionalTaskModal();

            // Reset form
            additionalTaskForm.reset();

            showMessage('Additional task created successfully!', 'success');
        });
    }

    // Cancel additional task
    const cancelAdditionalTaskBtn = document.getElementById('cancelAdditionalTask');
    if (cancelAdditionalTaskBtn) {
        cancelAdditionalTaskBtn.addEventListener('click', function() {
            hideAdditionalTaskModal();
        });
    }

    // Modal close buttons
    document.querySelectorAll('.modal-close, .modal-cancel').forEach(button => {
        button.addEventListener('click', function() {
            const modal = this.closest('.modal');
            if (modal) {
                hideModal(modal.id);
            }
        });
    });

    // Close modals when clicking outside
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', function(e) {
            if (e.target === this) {
                hideModal(this.id);
            }
        });
    });

    // Keyboard navigation for modals
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            const openModal = document.querySelector('.modal[aria-hidden="false"]');
            if (openModal) {
                hideModal(openModal.id);
            }
        }
    });

    // Search functionality for technician selection
    const technicianSearch = document.getElementById('technicianSearch');
    if (technicianSearch) {
        technicianSearch.addEventListener('input', function() {
            const searchTerm = this.value.toLowerCase();
            const techOptions = document.querySelectorAll('.technician-option');

            techOptions.forEach(option => {
                const techName = option.querySelector('.tech-name').textContent.toLowerCase();
                option.style.display = techName.includes(searchTerm) ? 'flex' : 'none';
            });
        });
    }
});
