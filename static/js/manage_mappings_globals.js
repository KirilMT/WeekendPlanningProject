// Global variables
let currentMappings = {};
let selectedTechnician = null;
let unsavedChanges = false;
let changesSummary = new Set();

let allTechnologies = [];
let allTechnologyGroups = [];
let allSpecialities = [];
let currentSelectedTechnicianId = null;

// DOM Element references
const technicianSelect = document.getElementById('technicianSelect');
const currentTechNameDisplay = document.getElementById('currentTechName');
const techSattelitePointInput = document.getElementById('techSattelitePoint');
const techLinesInput = document.getElementById('techLines');
const taskListDiv = document.getElementById('taskList');
const addTaskBtn = document.getElementById('addTaskBtn');
const saveChangesBtn = document.getElementById('saveChangesBtn');
const statusMessageDiv = document.getElementById('statusMessage');
const backToDashboardBtn = document.getElementById('backToDashboardBtn');

const technologyListContainerDiv = document.getElementById('technologyListContainer');
const newTechnologyNameInput = document.getElementById('newTechnologyName');
const addTechnologyBtn = document.getElementById('addTechnologyBtn');
const technicianSkillsListContainerDiv = document.getElementById('technicianSkillsListContainer');

const technologyGroupListContainerDiv = document.getElementById('technologyGroupListContainer');
const newTechnologyGroupNameInput = document.getElementById('newTechnologyGroupName');
const addTechnologyGroupBtn = document.getElementById('addTechnologyGroupBtn');
const newTechnologyGroupSelect = document.getElementById('newTechnologyGroupSelect');
const newTechnologyParentSelect = document.getElementById('newTechnologyParentSelect');

const specialityListContainerDiv = document.getElementById('specialityListContainer');
const newSpecialityNameInput = document.getElementById('newSpecialityName');
const addSpecialityBtn = document.getElementById('addSpecialityBtn');
const assignSpecialitySelect = document.getElementById('assignSpecialitySelect');
const assignSpecialityBtn = document.getElementById('assignSpecialityBtn');
const technicianSpecialitiesContainerDiv = document.getElementById('technicianSpecialitiesContainer');

// New DOM element for Task-Technology Mappings
const taskTechnologyMappingListContainerDiv = document.getElementById('taskTechnologyMappingListContainer');
// DOM elements for the new "Add Task" form in Task-Technology Mappings section
const newTaskNameForMappingInput = document.getElementById('newTaskNameForMapping');
const newTaskTechnologySelectForMapping = document.getElementById('newTaskTechnologySelectForMapping');
const addNewTaskForMappingBtn = document.getElementById('addNewTaskForMappingBtn');


function updateSaveChangesButton() {
    if (saveChangesBtn) {
        const numChanges = changesSummary.size;
        if (numChanges > 0) {
            saveChangesBtn.textContent = `Save All Changes (${numChanges})`;
            saveChangesBtn.disabled = false;
        } else {
            saveChangesBtn.textContent = 'Save All Changes';
            saveChangesBtn.disabled = true; // Disable if no changes
        }
    }
}

function recordChange(type, entityId = null, field = null, oldValue = null, newValue = null, entityName = null, additionalInfo = {}) {
    const timestamp = new Date().toISOString();
    const changeDetail = {
        type: type,
        description: `Field '${field}' for ${entityName || `ID: ${entityId}`} changed from '${oldValue}' to '${newValue}'`, // Generic description
        entity: entityName,
        entityId: entityId,
        field: field,
        oldValue: oldValue,
        newValue: newValue,
        timestamp: timestamp,
        ...additionalInfo
    };

    // More specific descriptions for certain types
    if (type === 'Task Assignment Add') {
        changeDetail.description = `Task '${additionalInfo.taskName}' assigned to ${entityName}`;
    } else if (type === 'Task Assignment Remove') {
        changeDetail.description = `Task '${additionalInfo.taskName}' unassigned from ${entityName}`;
    } else if (type === 'Task Priority Change') {
        changeDetail.description = `Priority of task '${additionalInfo.taskName}' for ${entityName} changed from ${oldValue} to ${newValue}`;
    } else if (type === 'New Task for Mapping') {
        changeDetail.description = `New task '${entityName}' added with technologies: ${additionalInfo.technologiesAssigned}`;
    } else if (type === 'Task Technology Update') {
        changeDetail.description = `Technologies for task '${entityName}' updated.` // oldValue/newValue for technologies can be complex, keep it simple
    } else if (type === 'Task Name Update') {
        changeDetail.description = `Task name for ID '${entityId}' changed from '${oldValue}' to '${newValue}'`
    } else if (type === 'Technology Add') {
        changeDetail.description = `New technology '${entityName}' added.`
        if (additionalInfo.groupName) changeDetail.description += ` to group '${additionalInfo.groupName}'`;
        if (additionalInfo.parentName) changeDetail.description += ` under parent '${additionalInfo.parentName}'`;
    } else if (type === 'Technology Group Add') {
        changeDetail.description = `New technology group '${entityName}' added.`
    } else if (type === 'Satellite Point Add') {
        changeDetail.description = `New satellite point '${entityName}' added.`
    } else if (type === 'Line Add') {
        changeDetail.description = `New line '${entityName}' added to satellite point '${additionalInfo.satellitePointName}'.`
    }

    changesSummary.add(JSON.stringify(changeDetail)); // Add detailed object
    unsavedChanges = true;
    updateSaveChangesButton();
    console.log('Change recorded:', changeDetail);
}

function clearUnsavedChanges() {
    unsavedChanges = false;
    changesSummary.clear();
    updateSaveChangesButton();
    if (statusMessageDiv) statusMessageDiv.textContent = '';
}
