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

// State management functions
let saveStateThrottle = null;
let lastStateSave = 0;

function savePageState() {
    // Throttle state saving to prevent excessive calls
    const now = Date.now();
    if (now - lastStateSave < 1000) { // Don't save more than once per second
        if (saveStateThrottle) clearTimeout(saveStateThrottle);
        saveStateThrottle = setTimeout(() => savePageState(), 1000);
        return;
    }
    lastStateSave = now;

    const dashboardButton = document.getElementById('openDashboardButton');
    const fileInput = document.getElementById('excelFile');
    const fileLabel = document.querySelector('.file-label');

    const state = {
        uploadedFile: uploadedFile ? {
            name: uploadedFile.name,
            size: uploadedFile.size,
            type: uploadedFile.type,
            lastModified: uploadedFile.lastModified
        } : null,
        repTasks,
        currentRepTaskIndex,
        repAssignments,
        presentTechnicians,
        eligibleTechnicians,
        filename,
        sessionId, // Keep the current session ID
        additionalTaskCounter,
        availableSkills,
        // Enhanced file state tracking
        fileInputState: {
            disabled: fileInput?.disabled || false,
            fileName: fileLabel?.textContent?.trim() || '',
            hasFile: !!(uploadedFile || filename),
            fileSelected: !!(fileInput?.files?.[0] || uploadedFile || filename),
            fileUploaded: !!(uploadedFile && filename) // Track if file was actually uploaded
        },
        // UI state with better detection
        dashboardButtonVisible: dashboardButton && (dashboardButton.style.display === 'inline-flex' ||
                                                   dashboardButton.style.display === 'block' ||
                                                   (!dashboardButton.style.display && getComputedStyle(dashboardButton).display !== 'none')),
        dashboardUrl: null, // Will be set below
        generateNewButtonExists: !!document.getElementById('generateNewDashboardBtn'),
        currentMessage: {
            text: document.getElementById('message')?.textContent || '',
            type: document.getElementById('message')?.className?.split(' ').find(cls => ['success', 'error', 'warning'].includes(cls)) || '',
            visible: document.getElementById('message')?.style.display === 'block'
        },
        submitButtonVisible: document.querySelector('#uploadForm button[type="submit"]')?.style.display !== 'none',
        // Add timestamp for cache management
        timestamp: Date.now(),
        version: '1.0' // For future compatibility
    };

    // Multiple approaches to get dashboard URL
    if (window.currentDashboardUrl) {
        state.dashboardUrl = window.currentDashboardUrl;
    } else if (dashboardButton && dashboardButton.onclick) {
        const onclickStr = dashboardButton.onclick.toString();
        const urlMatch = onclickStr.match(/window\.open\(['"]([^'"]+)['"]/);
        if (urlMatch) {
            state.dashboardUrl = urlMatch[1];
        }
    }

    console.log('Saving state:', {
        hasFile: state.fileInputState.hasFile,
        fileSelected: state.fileInputState.fileSelected,
        fileUploaded: state.fileInputState.fileUploaded,
        filename: state.filename,
        sessionId: state.sessionId,
        uploadedFile: !!state.uploadedFile,
        dashboardVisible: state.dashboardButtonVisible,
        dashboardUrl: state.dashboardUrl,
        globalUrl: window.currentDashboardUrl,
        timestamp: new Date(state.timestamp).toLocaleTimeString()
    });

    // Store with expiration management
    try {
        sessionStorage.setItem('weekendPlanningState', JSON.stringify(state));
        sessionStorage.setItem('weekendPlanningStateTimestamp', state.timestamp.toString());
    } catch (e) {
        console.warn('SessionStorage full, clearing old data:', e);
        clearExpiredStates();
        try {
            sessionStorage.setItem('weekendPlanningState', JSON.stringify(state));
            sessionStorage.setItem('weekendPlanningStateTimestamp', state.timestamp.toString());
        } catch (e2) {
            console.error('Failed to save state even after cleanup:', e2);
        }
    }
}

function restorePageState() {
    const savedState = sessionStorage.getItem('weekendPlanningState');
    const savedTimestamp = sessionStorage.getItem('weekendPlanningStateTimestamp');

    if (!savedState) return false;

    // Check if state is expired (older than 24 hours)
    if (savedTimestamp) {
        const stateAge = Date.now() - parseInt(savedTimestamp);
        const maxAge = 24 * 60 * 60 * 1000; // 24 hours
        if (stateAge > maxAge) {
            console.log('Saved state expired, clearing...');
            clearPageState();
            return false;
        }
    }

    try {
        const state = JSON.parse(savedState);
        console.log('Restoring state from:', new Date(state.timestamp || 0).toLocaleTimeString());

        // Restore application variables
        repTasks = state.repTasks || [];
        currentRepTaskIndex = state.currentRepTaskIndex || 0;
        repAssignments = state.repAssignments || [];
        presentTechnicians = state.presentTechnicians || [];
        eligibleTechnicians = state.eligibleTechnicians || {};
        filename = state.filename || '';

        // Check if session should be considered expired based on time away
        const timeAway = Date.now() - (state.timestamp || 0);
        const sessionTimeoutMs = 5 * 60 * 1000; // 5 minutes session timeout

        if (timeAway > sessionTimeoutMs) {
            // Session expired due to time - generate new session ID
            sessionId = generateSessionId();
            console.log('Session expired due to time away:', Math.round(timeAway / 1000), 'seconds');
        } else {
            // Session still valid - keep the same session ID
            sessionId = state.sessionId || generateSessionId();
            console.log('Session restored, time away:', Math.round(timeAway / 1000), 'seconds');
        }

        additionalTaskCounter = state.additionalTaskCounter || 0;
        availableSkills = state.availableSkills || [];

        // Enhanced file state restoration
        const fileInput = document.getElementById('excelFile');
        if (state.fileInputState?.fileSelected || state.uploadedFile?.name || state.filename) {
            const restoredFileName = state.uploadedFile?.name || state.filename;
            if (restoredFileName) {
                filename = restoredFileName;
                updateFileDisplay(restoredFileName);

                // Check if file upload is still valid based on session status
                const needsReupload = timeAway > sessionTimeoutMs;

                window.restoredFileData = {
                    name: restoredFileName,
                    hasData: true,
                    needsReupload: needsReupload
                };

                console.log('File state restored:', restoredFileName, 'needsReupload:', needsReupload, needsReupload ? '(session expired)' : '(session valid)');
            }
        }

        // Restore UI state
        if (state.fileInputState?.disabled) {
            disableFileInput();
        }

        if (!state.submitButtonVisible) {
            const submitBtn = document.querySelector('#uploadForm button[type="submit"]');
            if (submitBtn) {
                submitBtn.style.display = 'none';
            }
        }

        // Restore dashboard button with proper functionality
        if (state.dashboardButtonVisible && state.dashboardUrl) {
            const openDashboardButton = document.getElementById('openDashboardButton');
            if (openDashboardButton) {
                openDashboardButton.style.display = 'inline-flex';
                openDashboardButton.onclick = () => window.open(state.dashboardUrl, '_blank');
                window.currentDashboardUrl = state.dashboardUrl; // Restore global URL
            }
        } else if (state.dashboardButtonVisible) {
            const openDashboardButton = document.getElementById('openDashboardButton');
            if (openDashboardButton) {
                openDashboardButton.style.display = 'inline-flex';
            }
        }

        if (state.generateNewButtonExists) {
            showGenerateNewDashboardButton();
        }

        if (state.currentMessage?.visible && state.currentMessage?.text) {
            showMessage(state.currentMessage.text, state.currentMessage.type);
        }

        return true;
    } catch (error) {
        console.error('Error restoring page state:', error);
        clearPageState();
        return false;
    }
}

function clearPageState() {
    sessionStorage.removeItem('weekendPlanningState');
    sessionStorage.removeItem('weekendPlanningStateTimestamp');
    window.restoredFileData = null;
}

// Cache management functions
function clearExpiredStates() {
    const keys = Object.keys(sessionStorage);
    keys.forEach(key => {
        if (key.startsWith('weekendPlanning') || key.includes('State')) {
            try {
                sessionStorage.removeItem(key);
            } catch (e) {
                console.warn('Could not remove expired state:', key);
            }
        }
    });
}

// Generate a simple session ID
function generateSessionId() {
    return Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
}

// Cleanup on page visibility change (user switches tabs/windows)
document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
        savePageState();
    }
});

// Periodic cleanup every 30 minutes
setInterval(() => {
    const timestamp = sessionStorage.getItem('weekendPlanningStateTimestamp');
    if (timestamp) {
        const age = Date.now() - parseInt(timestamp);
        // Clean up if older than 12 hours
        if (age > 12 * 60 * 60 * 1000) {
            console.log('Performing periodic state cleanup...');
            clearExpiredStates();
        }
    }
}, 30 * 60 * 1000); // Every 30 minutes

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

        // Organize skills by groups and parent-child relationships
        const skillsByGroup = {};
        const parentSkills = new Map();
        const childSkills = new Map();

        // First pass: categorize skills by group and identify parent-child relationships
        availableSkills.forEach(skill => {
            const groupName = skill.group_name || 'Other';
            if (!skillsByGroup[groupName]) {
                skillsByGroup[groupName] = [];
            }
            skillsByGroup[groupName].push(skill);

            // Build parent-child maps
            if (skill.parent_id) {
                if (!childSkills.has(skill.parent_id)) {
                    childSkills.set(skill.parent_id, []);
                }
                childSkills.get(skill.parent_id).push(skill);
            } else {
                // This is a parent skill or standalone skill
                if (!parentSkills.has(skill.id)) {
                    parentSkills.set(skill.id, skill);
                }
            }
        });

        // Create organized options
        const sortedGroups = Object.keys(skillsByGroup).sort();

        sortedGroups.forEach(groupName => {
            // Add group header
            const groupHeader = document.createElement('optgroup');
            groupHeader.label = `📁 ${groupName}`;
            skillsSelect.appendChild(groupHeader);

            const groupSkills = skillsByGroup[groupName];

            // Sort skills within group: parents first, then children
            const parentSkillsInGroup = groupSkills.filter(skill => !skill.parent_id);
            const childSkillsInGroup = groupSkills.filter(skill => skill.parent_id);

            // Add parent skills and their children
            parentSkillsInGroup.forEach(parentSkill => {
                const parentOption = document.createElement('option');
                parentOption.value = parentSkill.id;
                parentOption.textContent = `🔧 ${parentSkill.name}`;
                parentOption.className = 'parent-skill';
                groupHeader.appendChild(parentOption);

                // Add children of this parent
                const children = childSkillsInGroup.filter(child => child.parent_id === parentSkill.id);
                children.forEach(childSkill => {
                    const childOption = document.createElement('option');
                    childOption.value = childSkill.id;
                    childOption.textContent = `    ↳ 🔩 ${childSkill.name}`;
                    childOption.className = 'child-skill';
                    groupHeader.appendChild(childOption);
                });
            });

            // Add orphaned child skills (children whose parents are not in this group)
            const orphanedChildren = childSkillsInGroup.filter(child =>
                !parentSkillsInGroup.some(parent => parent.id === child.parent_id)
            );
            orphanedChildren.forEach(childSkill => {
                const childOption = document.createElement('option');
                childOption.value = childSkill.id;
                childOption.textContent = `🔩 ${childSkill.name}`;
                childOption.className = 'orphaned-child-skill';
                groupHeader.appendChild(childOption);
            });
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

let isUploadInProgress = false;

// Improved message display function
function showMessage(text, type) {
    const messageDiv = document.getElementById('message');
    if (messageDiv) {
        // Clear any existing message first
        messageDiv.style.display = 'none';

        // Force reflow to ensure the hide takes effect
        messageDiv.offsetHeight;

        // Set new message
        messageDiv.style.display = 'block';
        messageDiv.className = `message-container ${type}`;
        messageDiv.textContent = text;
        messageDiv.style.position = 'fixed';
        messageDiv.style.top = '20px';
        messageDiv.style.left = '50%';
        messageDiv.style.transform = 'translateX(-50%)';
        messageDiv.style.zIndex = '10000';

        // Force the element to be visible and scroll into view
        messageDiv.scrollIntoView({behavior: 'smooth', block: 'center'});

        console.log(`Message displayed: [${type.toUpperCase()}] ${text}`);

        // Auto-hide messages after appropriate time
        const hideTimeout = type === 'error' ? 8000 : 4000; // Longer for errors
        setTimeout(() => {
            if (messageDiv.style.display === 'block' && messageDiv.textContent === text) {
                messageDiv.style.display = 'none';
            }
        }, hideTimeout);
    } else {
        console.error("INDEX.HTML: Message div not found!");
        // Fallback to browser alert for critical errors
        if (type === 'error') {
            alert(`Error: ${text}`);
        }
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
    console.log('INDEX.HTML: showTaskAssignmentModal called, currentRepTaskIndex:', currentRepTaskIndex, 'repTasks length:', repTasks.length);

    if (currentRepTaskIndex < repTasks.length) {
        const task = repTasks[currentRepTaskIndex];
        console.log('INDEX.HTML: Current task for modal:', task);

        const taskInfoDiv = document.getElementById('taskInfo');
        if (taskInfoDiv) {
            // Simple ticket info display matching the original showRepModal format
            taskInfoDiv.innerHTML = `
                <p><strong>Task:</strong> ${task.name || task.scheduler_group_task || 'Unknown Task'}</p>
                <p><strong>Ticket/MO:</strong> ${task.ticket_mo || 'N/A'}</p>
                ${task.ticket_url ? `<p><strong>Link:</strong> <a href="${task.ticket_url}" target="_blank">${task.ticket_url}</a></p>` : ''}
                <p><strong>Technicians Planned:</strong> ${task.mitarbeiter_pro_aufgabe}</p>
                <p><strong>Duration:</strong> ${task.planned_worktime_min} minutes</p>
                <p><strong>Progress:</strong> ${currentRepTaskIndex + 1} of ${repTasks.length}</p>
                ${task.isAdditionalTask ? '<p><span class="additional-task-badge">Additional Task</span></p>' : ''}
            `;
        } else {
            console.error("INDEX.HTML: taskInfo div not found!");
        }

        populateTaskTechnicians(task);

        // Clear search input and show modal
        const technicianSearch = document.getElementById('technicianSearch');
        if (technicianSearch) technicianSearch.value = '';

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
        techDiv.style.cursor = 'pointer';
        techDiv.style.padding = '8px';
        techDiv.style.border = '1px solid #ddd';
        techDiv.style.borderRadius = '4px';
        techDiv.style.marginBottom = '4px';
        techDiv.style.display = 'flex';
        techDiv.style.alignItems = 'center';

        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.id = `tech_${tech.name}`;
        checkbox.value = tech.name;
        checkbox.name = 'selectedTechnicians';
        checkbox.style.marginRight = '8px';

        const label = document.createElement('label');
        // REMOVED: label.htmlFor = `tech_${tech.name}`; - This was causing the conflict
        label.className = 'tech-name';
        label.textContent = tech.name;
        label.style.cursor = 'pointer';
        label.style.flex = '1';
        label.style.margin = '0';
        label.style.userSelect = 'none'; // Prevent text selection when clicking

        // Make the entire div clickable - improved event handler
        techDiv.addEventListener('click', function(e) {
            // If clicking directly on the checkbox, let it handle its own state
            if (e.target === checkbox) {
                // Don't prevent default behavior for checkbox clicks
                // Just update the visual feedback after the checkbox state changes
                setTimeout(() => {
                    updateVisualFeedback();
                }, 0);
                return;
            }

            // For clicks anywhere else in the div, toggle the checkbox
            e.preventDefault();
            e.stopPropagation();

            checkbox.checked = !checkbox.checked;
            updateVisualFeedback();
        });

        // Function to update visual feedback based on checkbox state
        function updateVisualFeedback() {
            if (checkbox.checked) {
                techDiv.style.backgroundColor = '#e3f2fd';
                techDiv.style.borderColor = '#2196f3';
            } else {
                techDiv.style.backgroundColor = '';
                techDiv.style.borderColor = '#ddd';
            }
        }

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
            // Store the dashboard URL globally for state management
            window.currentDashboardUrl = data.dashboard_url;

            const openDashboardButton = document.getElementById('openDashboardButton');
            if (openDashboardButton) {
                openDashboardButton.onclick = () => window.open(data.dashboard_url, '_blank');
                openDashboardButton.style.display = 'inline-flex';
            }

            // Show the "Generate New Dashboard" button after successful generation
            showGenerateNewDashboardButton();

            // Save state immediately after dashboard is generated
            savePageState();
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
    // Clear saved state
    clearPageState();

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

    // Clear any saved state on page refresh (F5 or manual refresh)
    // Only restore state when navigating back from other pages
    const isPageRefresh = performance.navigation.type === performance.navigation.TYPE_RELOAD;
    if (isPageRefresh) {
        clearPageState();
        console.log('Page refreshed - cleared saved state');
    } else {
        // Try to restore previous state only when navigating back
        const stateRestored = restorePageState();
        console.log('State restoration result:', stateRestored);
    }

    // Save state before navigating away
    window.addEventListener('beforeunload', function() {
        savePageState();
    });

    // Specifically handle the Manage Skills & Mappings button
    const manageMappingsBtn = document.getElementById('manageMappingsBtn');
    if (manageMappingsBtn) {
        manageMappingsBtn.addEventListener('click', function(e) {
            savePageState();
        });
    }

    // Save state when clicking on other external links
    document.querySelectorAll('a[href]:not([href^="#"]), button[onclick*="window.location"]').forEach(element => {
        if (element.id !== 'manageMappingsBtn') {
            element.addEventListener('click', function() {
                savePageState();
            });
        }
    });

    // Upload form handler with improved error handling
    const uploadForm = document.getElementById('uploadForm');
    if (uploadForm) {
        uploadForm.addEventListener('submit', function(e) {
            e.preventDefault();

            // Prevent duplicate uploads
            if (isUploadInProgress) {
                console.log('Upload already in progress, ignoring duplicate request');
                return;
            }

            const fileInput = document.getElementById('excelFile');
            let hasRestoredFile = window.restoredFileData?.hasData && filename;

            // Check if restored file needs re-upload due to session expiration
            if (hasRestoredFile && window.restoredFileData?.needsReupload) {
                // File was restored but session expired - need actual file upload
                if (!fileInput || !fileInput.files[0]) {
                    showMessage('Session expired. Please re-select and upload your Excel file.', 'error');
                    // Reset the file display to show that re-upload is needed
                    updateFileDisplay(`${filename} (Please re-select)`);
                    enableFileInput(); // Re-enable file input for new selection
                    window.restoredFileData = null;
                    return;
                }
                // User has selected a new file, proceed with normal upload
                hasRestoredFile = false;
            }

            // Allow submission if we have either a new file or valid restored file state
            if (!hasRestoredFile && (!fileInput || !fileInput.files[0])) {
                showMessage('Please select an Excel file.', 'error');
                return;
            }

            // Use existing file data if we have it from restored state (no re-upload needed)
            if (hasRestoredFile && filename && !window.restoredFileData?.needsReupload) {
                savePageState();
                showAbsentModal();
                return;
            }

            // Handle new file upload
            uploadedFile = fileInput.files[0];
            filename = uploadedFile.name;

            updateFileDisplay(filename);
            savePageState();

            const formData = new FormData();
            formData.append('csrf_token', getCSRFToken());
            formData.append('excelFile', uploadedFile);
            formData.append('session_id', sessionId);

            // Set upload in progress flag
            isUploadInProgress = true;
            console.log('Starting file upload for:', filename);

            fetch('/upload', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                console.log('Upload response status:', response.status);
                // Handle both success and error responses
                return response.json().then(data => {
                    return { data, status: response.status, ok: response.ok };
                });
            })
            .then(({ data, status, ok }) => {
                if (!ok || data.error || (data.message && data.message.includes('mismatch'))) {
                    // Handle error cases
                    const errorMessage = data.error || data.message || `Upload failed (${status}). Please try again.`;
                    console.log('Upload error:', errorMessage);
                    showMessage(errorMessage, 'error');
                    return;
                }

                // Success - process the data
                console.log('Upload successful, proceeding to absent modal');
                repTasks = data.rep_tasks || [];
                eligibleTechnicians = data.eligible_technicians || {};
                savePageState();
                showAbsentModal();
            })
            .catch(error => {
                console.error('Upload request failed:', error);
                showMessage('Upload failed. Please check your connection and try again.', 'error');
            })
            .finally(() => {
                // Always reset the upload flag
                isUploadInProgress = false;
                console.log('Upload process completed');
            });
        });
    }

    // Submit button click handler to ensure form submission
    const submitButton = document.querySelector('#uploadForm button[type="submit"]');
    if (submitButton) {
        submitButton.addEventListener('click', function(e) {
            const form = submitButton.closest('form');
            if (form) {
                const submitEvent = new Event('submit', { bubbles: true, cancelable: true });
                form.dispatchEvent(submitEvent);
            }
        });
    }

    // File input change handler
    const fileInput = document.getElementById('excelFile');
    if (fileInput) {
        fileInput.addEventListener('change', function() {
            if (this.files && this.files[0]) {
                const selectedFile = this.files[0];

                uploadedFile = selectedFile;
                filename = selectedFile.name;

                updateFileDisplay(selectedFile.name);
                window.restoredFileData = null;
                savePageState();
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
            const currentTask = repTasks[currentRepTaskIndex];
            const requiredTechnicians = parseInt(currentTask.mitarbeiter_pro_aufgabe) || 1;

            // CRITICAL: Check if selected technicians count is less than required count
            if (selectedTechnicians.length < requiredTechnicians) {
                let message;
                if (selectedTechnicians.length === 0) {
                    message = `This task requires ${requiredTechnicians} technician${requiredTechnicians > 1 ? 's' : ''}. Please select ${requiredTechnicians} technician${requiredTechnicians > 1 ? 's' : ''}.`;
                } else {
                    message = `You have selected ${selectedTechnicians.length} technician${selectedTechnicians.length > 1 ? 's' : ''}, but this task requires ${requiredTechnicians} technician${requiredTechnicians > 1 ? 's' : ''}. Please select ${requiredTechnicians - selectedTechnicians.length} more technician${(requiredTechnicians - selectedTechnicians.length) > 1 ? 's' : ''}.`;
                }
                showMessage(message, 'error');
                return; // Stop here, don't close modal
            }

            // CRITICAL: Store assignment data with exact counts for backend processing
            repAssignments.push({
                task_id: currentTask.id,
                task_name: currentTask.name || currentTask.scheduler_group_task,
                technicians: selectedTechnicians, // Backend expects 'technicians' field
                required_technicians: requiredTechnicians, // CRITICAL: Backend needs to know required count
                selected_count: selectedTechnicians.length, // CRITICAL: Backend needs to know selected count
                skipped: false // Explicitly mark as not skipped
            });

            console.log('Task assigned:', {
                task_id: currentTask.id,
                task_name: currentTask.name || currentTask.scheduler_group_task,
                technicians: selectedTechnicians,
                required_count: requiredTechnicians,
                selected_count: selectedTechnicians.length
            });

            currentRepTaskIndex++;

            // Check if this was the last task
            if (currentRepTaskIndex >= repTasks.length) {
                // Close REP modal before showing progress
                hideTaskAssignmentModal();
                // Submit final assignments which will show progress bar
                submitFinalAssignments();
            } else {
                // Show next task directly without closing modal
                showTaskAssignmentModal();
            }
        });
    }

    const skipTaskBtn = document.getElementById('skipTask');
    if (skipTaskBtn) {
        skipTaskBtn.addEventListener('click', function() {
            const currentTask = repTasks[currentRepTaskIndex];

            // CRITICAL: Show prompt for skip reason - this is required by the backend
            const skipReason = prompt('Please provide a reason for skipping this task:', '');

            // If user cancels the prompt, don't skip the task
            if (skipReason === null) {
                return;
            }

            // If user provides empty reason, ask for a valid reason
            if (skipReason.trim() === '') {
                showMessage('Please provide a valid reason for skipping this task.', 'error');
                return;
            }

            // CRITICAL: Store skip data in the format expected by backend
            repAssignments.push({
                task_id: currentTask.id,
                task_name: currentTask.name || currentTask.scheduler_group_task,
                technicians: [], // Empty technicians array for skipped tasks
                skipped: true, // CRITICAL: Backend checks for this flag
                skip_reason: skipReason.trim() // CRITICAL: Backend uses this for reporting
            });

            console.log('Task skipped:', {
                task_id: currentTask.id,
                task_name: currentTask.name || currentTask.scheduler_group_task,
                skip_reason: skipReason.trim(),
                skipped: true
            });

            currentRepTaskIndex++;
            // Don't hide modal, just show next task directly
            showTaskAssignmentModal(); // This will show next task or finish
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

            // Fetch eligible technicians for the new task
            fetch('/api/eligible_technicians_for_task', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': getCSRFToken()
                },
                body: JSON.stringify({
                    required_skills: taskData.required_skills,
                    present_technicians: presentTechnicians
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    showMessage(data.error, 'error');
                    return;
                }
                eligibleTechnicians[taskData.id] = data;
                repTasks.push(taskData);
                hideAdditionalTaskModal();
                additionalTaskForm.reset();
                showMessage('Additional task created successfully!', 'success');
            })
            .catch(error => {
                console.error('Error fetching eligible technicians for additional task:', error);
                showMessage('Could not create additional task. Please try again.', 'error');
            });
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
