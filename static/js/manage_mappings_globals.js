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

