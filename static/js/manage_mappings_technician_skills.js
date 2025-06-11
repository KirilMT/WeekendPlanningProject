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

function renderTechnicianSkills() {
    technicianSkillsListContainerDiv.innerHTML = '';
    if (!selectedTechnician || !currentMappings.technicians[selectedTechnician]) {
        technicianSkillsListContainerDiv.innerHTML = '<p>Select technician to view skills.</p>';
        return;
    }
    if (allTechnologies.length === 0) {
        technicianSkillsListContainerDiv.innerHTML = '<p>No technologies defined. Skills cannot be assigned.</p>';
        return;
    }
    const techSkills = currentMappings.technicians[selectedTechnician].skills || {};

    const hasChildren = (technologyId) => {
        return allTechnologies.some(tech => tech.parent_id === technologyId);
    };

    function renderSkillItemsRecursive(parentElement, parentTechnologyId, level) {
        const childrenOfParent = allTechnologies.filter(tech => tech.parent_id === parentTechnologyId);
        childrenOfParent.sort((a, b) => a.name.localeCompare(b.name));

        childrenOfParent.forEach(childTech => {
            const skillDiv = document.createElement('div');
            skillDiv.classList.add('skill-item');
            skillDiv.style.marginLeft = `${level * 25}px`;

            const skillLabel = document.createElement('label');
            skillLabel.className = 'skill-label';
            skillLabel.textContent = escapeHtml(childTech.name);
            skillLabel.setAttribute('for', `skill-${childTech.id}-select`);
            skillDiv.appendChild(skillLabel);

            if (!hasChildren(childTech.id)) {
                const skillSelect = document.createElement('select');
                skillSelect.id = `skill-${childTech.id}-select`;
                skillSelect.dataset.technologyId = childTech.id;
                ["Not Skilled (0)", "Beginner (1)", "Intermediate (2)", "Advanced (3)", "Expert (4)"].forEach((lvlText, idx) => {
                    const option = document.createElement('option');
                    option.value = idx;
                    option.textContent = lvlText;
                    if (techSkills[childTech.id] === idx) option.selected = true;
                    skillSelect.appendChild(option);
                });
                skillSelect.addEventListener('change', async (e) => {
                    await updateTechnicianSkill(selectedTechnician, currentSelectedTechnicianId, parseInt(e.target.dataset.technologyId), parseInt(e.target.value));
                });
                skillDiv.appendChild(skillSelect);
            }
            parentElement.appendChild(skillDiv);

            if (hasChildren(childTech.id)) {
                renderSkillItemsRecursive(parentElement, childTech.id, level + 1);
            }
        });
    }

    const topLevelTechnologies = allTechnologies.filter(tech => tech.parent_id === null);
    topLevelTechnologies.sort((a, b) => {
        const groupCompare = (a.group_name || 'ZZZ_Uncategorized').localeCompare(b.group_name || 'ZZZ_Uncategorized');
        if (groupCompare !== 0) return groupCompare;
        return a.name.localeCompare(b.name);
    });

    let currentGroupName = null;
    topLevelTechnologies.forEach(topLevelTech => {
        if (topLevelTech.group_name !== currentGroupName) {
            const groupHeader = document.createElement('h4');
            groupHeader.textContent = escapeHtml(topLevelTech.group_name || 'Uncategorized');
            groupHeader.classList.add('skill-group-header');
            technicianSkillsListContainerDiv.appendChild(groupHeader);
            currentGroupName = topLevelTech.group_name;
        }

        const skillDiv = document.createElement('div');
        skillDiv.classList.add('skill-item');
        skillDiv.style.marginLeft = '0px';

        const skillLabel = document.createElement('label');
        skillLabel.className = 'skill-label';
        skillLabel.textContent = escapeHtml(topLevelTech.name);
        skillLabel.setAttribute('for', `skill-${topLevelTech.id}-select`);
        skillDiv.appendChild(skillLabel);

        if (!hasChildren(topLevelTech.id)) {
            const skillSelect = document.createElement('select');
            skillSelect.id = `skill-${topLevelTech.id}-select`;
            skillSelect.dataset.technologyId = topLevelTech.id;
            ["Not Skilled (0)", "Beginner (1)", "Intermediate (2)", "Advanced (3)", "Expert (4)"].forEach((lvlText, idx) => {
                const option = document.createElement('option');
                option.value = idx;
                option.textContent = lvlText;
                if (techSkills[topLevelTech.id] === idx) option.selected = true;
                skillSelect.appendChild(option);
            });
            skillSelect.addEventListener('change', async (e) => {
                await updateTechnicianSkill(selectedTechnician, currentSelectedTechnicianId, parseInt(e.target.dataset.technologyId), parseInt(e.target.value));
            });
            skillDiv.appendChild(skillSelect);
        }
        technicianSkillsListContainerDiv.appendChild(skillDiv);

        if (hasChildren(topLevelTech.id)) {
            renderSkillItemsRecursive(technicianSkillsListContainerDiv, topLevelTech.id, 1);
        }
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
            displayMessage(`Skill for tech ID ${technologyId} updated.`, 'success');
            if (!currentMappings.technicians[selectedTechnician].skills) currentMappings.technicians[selectedTechnician].skills = {};
            currentMappings.technicians[selectedTechnician].skills[technologyId] = skillLevel;
            recordChange(`Skill for ${escapeHtml(technicianName)} on tech ID ${technologyId} changed to ${skillLevel}`);
        } else {
            throw new Error(result.message || `Server error ${response.status}`);
        }
    } catch (error) {
        displayMessage(`Error updating skill: ${error.message}`, 'error');
        console.error(error);
        await fetchTechnicianSkills(selectedTechnician); // Revert UI
    }
}

