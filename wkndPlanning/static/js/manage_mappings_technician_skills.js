// --- Technician Skill Management ---
async function fetchTechnicianSkills(technicianName) {
    if (!technicianName || !currentSelectedTechnicianId) {
        renderTechnicianSkills();
        return;
    }
    try {
        const response = await fetch(`/api/technician_skills/${currentSelectedTechnicianId}`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const skillsData = await response.json();
        currentMappings.technicians[technicianName].skills = skillsData.skills || {};
        renderTechnicianSkills();
    } catch (error) {
        displayMessage(`Error fetching skills for ${technicianName}: ${error.message}`, 'error');
        console.error('Error fetching skills:', error);
        if (currentMappings.technicians && currentMappings.technicians[technicianName]) {
            currentMappings.technicians[technicianName].skills = {};
        }
        renderTechnicianSkills();
    }
}

const SKILL_LEVEL_TEXTS = ["Not Skilled (0)", "Beginner (1)", "Intermediate (2)", "Advanced (3)", "Expert (4)"];
const SKILL_LEVEL_NAMES = ["Not Skilled", "Beginner", "Intermediate", "Advanced", "Expert"];

function renderTechnicianSkills() {
    technicianSkillsListContainerDiv.innerHTML = '';
    if (!selectedTechnician || !currentMappings.technicians[selectedTechnician]) {
        technicianSkillsListContainerDiv.innerHTML = '<p>Select a technician to view their skills.</p>';
        return;
    }
    if (allTechnologies.length === 0) {
        technicianSkillsListContainerDiv.innerHTML = '<p>No technologies have been defined. Skills cannot be assigned.</p>';
        return;
    }

    technicianSkillsListContainerDiv.className = 'skills-tree-container';

    const techSkills = currentMappings.technicians[selectedTechnician].skills || {};
    const hasChildren = (technologyId) => allTechnologies.some(tech => tech.parent_id === technologyId);

    const createSkillViewMode = (technology, currentLevel) => {
        const container = document.createElement('div');
        container.classList.add('skill-level-container');

        if (hasChildren(technology.id)) {
            const parentSkillText = document.createElement('span');
            parentSkillText.classList.add('skill-level-text', 'parent-skill-indicator');
            parentSkillText.textContent = 'N/A (Parent Skill)';
            parentSkillText.title = 'This technology is a parent and cannot have a skill level directly assigned.';
            container.appendChild(parentSkillText);
        } else {
            const levelDisplay = document.createElement('div');
            levelDisplay.classList.add('legend-item-display');

            const badge = document.createElement('span');
            badge.classList.add('level-badge', `level-${currentLevel}`);
            badge.textContent = currentLevel;
            badge.title = `Level: ${SKILL_LEVEL_NAMES[currentLevel]}`;
            levelDisplay.appendChild(badge);
            
            container.appendChild(levelDisplay);

            const editButton = document.createElement('button');
            editButton.classList.add('btn', 'btn-warning', 'btn-sm');
            editButton.innerHTML = '<span class="btn-icon">✏️</span> Edit';
            editButton.addEventListener('click', () => {
                const skillItemDiv = container.closest('.skill-item-controls');
                skillItemDiv.innerHTML = ''; // Clear view mode
                skillItemDiv.appendChild(createSkillEditMode(technology, currentLevel));
            });
            container.appendChild(editButton);
        }

        if (hasChildren(technology.id)) {
            if (typeof techSkills[technology.id] !== 'undefined') {
                 displayMessage(`Skill '${escapeHtml(technology.name)}' for ${escapeHtml(selectedTechnician)} is now a parent skill and its level is no longer applicable.`, 'warning');
            }
        }
        return container;
    };

    const createSkillEditMode = (technology, currentLevel) => {
        const container = document.createElement('div');
        container.classList.add('skill-level-container', 'edit-mode');

        const skillSelect = document.createElement('select');
        skillSelect.id = `skill-${technology.id}-select`;
        skillSelect.dataset.technologyId = technology.id;
        SKILL_LEVEL_TEXTS.forEach((lvlText, idx) => {
            const option = document.createElement('option');
            option.value = idx;
            option.textContent = lvlText;
            if (currentLevel === idx) option.selected = true;
            skillSelect.appendChild(option);
        });
        container.appendChild(skillSelect);

        skillSelect.addEventListener('change', async () => {
            const newLevel = parseInt(skillSelect.value);
            await updateTechnicianSkill(selectedTechnician, currentSelectedTechnicianId, technology.id, newLevel);
        });

        return container;
    };

    function renderSkillNode(parentElement, technology, level) {
        const listItem = document.createElement('li');
        listItem.classList.add('skill-tree-item', `level-${level}`);
        listItem.dataset.techId = technology.id;

        const itemContent = document.createElement('div');
        itemContent.classList.add('skill-item-content');

        const skillLabel = document.createElement('span');
        skillLabel.className = 'skill-label';
        skillLabel.textContent = escapeHtml(technology.name);
        itemContent.appendChild(skillLabel);

        const controlsDiv = document.createElement('div');
        controlsDiv.classList.add('skill-item-controls');

        if (!hasChildren(technology.id)) {
            const currentSkillLevel = techSkills[technology.id] !== undefined ? parseInt(techSkills[technology.id], 10) : 0;
            controlsDiv.appendChild(createSkillViewMode(technology, currentSkillLevel));
        } else {
            const parentIndicator = document.createElement('span');
            parentIndicator.className = 'parent-indicator';
            controlsDiv.appendChild(parentIndicator);
        }
        itemContent.appendChild(controlsDiv);
        listItem.appendChild(itemContent);

        const children = allTechnologies.filter(tech => tech.parent_id === technology.id);
        if (children.length > 0) {
            const sublist = document.createElement('ul');
            sublist.classList.add('skill-subtree');
            children.sort((a, b) => a.name.localeCompare(b.name));
            children.forEach(child => renderSkillNode(sublist, child, level + 1));
            listItem.appendChild(sublist);
        }

        parentElement.appendChild(listItem);
    }

    const technologiesByGroup = allTechnologies.reduce((acc, tech) => {
        if (tech.parent_id === null) {
            const groupName = tech.group_name || 'Uncategorized';
            if (!acc[groupName]) {
                acc[groupName] = [];
            }
            acc[groupName].push(tech);
        }
        return acc;
    }, {});

    const sortedGroupNames = Object.keys(technologiesByGroup).sort((a, b) => {
        if (a === 'Uncategorized') return 1;
        if (b === 'Uncategorized') return -1;
        return a.localeCompare(b);
    });

    const rootList = document.createElement('ul');
    rootList.className = 'skill-tree';
    technicianSkillsListContainerDiv.appendChild(rootList);

    sortedGroupNames.forEach(groupName => {
        const groupLi = document.createElement('li');
        groupLi.className = 'skill-group';
        
        const groupHeader = document.createElement('h4');
        groupHeader.className = 'skill-group-header';
        groupHeader.textContent = escapeHtml(groupName);
        groupLi.appendChild(groupHeader);
        
        const groupSublist = document.createElement('ul');
        groupSublist.className = 'skill-subtree group-subtree';
        groupLi.appendChild(groupSublist);

        const topLevelTechs = technologiesByGroup[groupName];
        topLevelTechs.sort((a, b) => a.name.localeCompare(b.name));
        
        topLevelTechs.forEach(tech => {
            renderSkillNode(groupSublist, tech, 0);
        });
        
        rootList.appendChild(groupLi);
    });
}


async function updateTechnicianSkill(technicianName, technicianId, technologyId, skillLevel) {
    if (!technicianName || typeof technicianId === 'undefined') {
        displayMessage('Technician not selected for skill update.', 'error');
        return;
    }
    try {
        const response = await fetch('/api/technician_skill', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({technician_id: technicianId, technology_id: technologyId, skill_level: skillLevel}),
        });
        const result = await response.json();
        if (response.ok) {
            const technology = allTechnologies.find(t => t.id === parseInt(technologyId));
            const technologyName = technology ? technology.name : 'Unknown Skill';
            const techNameForMsg = technicianName || 'Selected Technician';

            displayMessage(`Skill '${escapeHtml(technologyName)}' for technician '${escapeHtml(techNameForMsg)}' updated to level ${escapeHtml(SKILL_LEVEL_TEXTS[skillLevel] || skillLevel)}.`, 'success');

            if (typeof fetchMappings === 'function' && technicianName) {
                await fetchMappings(technicianName);
            } else {
                console.error('fetchMappings function is not available or technicianName is missing. Cannot refresh full technician details.');
                renderTechnicianSkills();
            }
        } else {
            throw new Error(result.message || `Server error ${response.status}`);
        }
    } catch (error) {
        displayMessage(`Error updating skill: ${error.message}`, 'error');
        console.error(error);
        if (typeof fetchMappings === 'function' && selectedTechnician) { 
            await fetchMappings(selectedTechnician);
        } else {
            await fetchTechnicianSkills(selectedTechnician); 
        }
    }
}
