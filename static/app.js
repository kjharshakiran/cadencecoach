// --- Configuration ---
const APP_NAME = "CADENCECOACH";
const PRIMARY_COLOR = 'text-yellow-400';
const ACCENT_BG = 'bg-yellow-400';
const ACCENT_RING = 'ring-yellow-400';
const BG_COLOR = 'bg-gray-900';
const CARD_COLOR = 'bg-gray-800';

// --- State ---
let state = {
    page: 1,
    userData: {
        name: '',
        fitnessGoal: '',
        motivation: '',
        targetDate: '',
        dob: '',
        weight: '',
        gender: 'Male',
        height: '',
        wakeTime: '07:00',
        sleepTime: '23:00',
        access: 'Home',
        diet: 'Non-Vegetarian',
        streaks: [],
        notification: {
            email: true,
            chat: false,
            whatsapp: false
        }
    },
    plan: null,
    loadingPlan: false,
    error: ''
};

const microHabits = [
    { id: 'ice_packs', name: 'Ice packs / Cold plunge (5 min)', icon: '🧊', category: 'Recovery' },
    { id: 'face_washes', name: 'Face washes (3x daily)', icon: '💧', category: 'Hygiene' },
    { id: 'water_2l', name: 'Drink 2 liters of water', icon: '🥤', category: 'Nutrition' },
    { id: 'steps', name: 'Achieve 10,000 steps', icon: '👟', category: 'Movement' },
    { id: 'fasting', name: 'Occasional fasting (14-16 hrs)', icon: '🌙', category: 'Nutrition' },
    { id: 'vitamins', name: 'Take prescribed vitamins', icon: '💊', category: 'Nutrition' },
    { id: 'stand_hr', name: 'Stand for 1 hour of desk work', icon: '🧍', category: 'Posture' },
    { id: 'eye_massage', name: 'Eye massage (5 min)', icon: '👁️', category: 'Recovery' },
    { id: 'reading', name: 'Read 10 pages before sleep', icon: '📚', category: 'Mind' },
    { id: 'journal', name: '5 minutes of gratitude journaling', icon: '✍️', category: 'Mind' },
];

const mockPlan = {
    milestones: [
        { title: "Phase 1: Foundation (Weeks 1-4)", description: "Establish consistency, caloric awareness, and form mastery." },
        { title: "Phase 2: Intensity Build (Weeks 5-8)", description: "Increase weight/reps, introduce HIIT, and optimize sleep routine." },
        { title: "Phase 3: Peak Performance (Weeks 9-12)", description: "Max out major lifts, integrate advanced recovery, and hit target weight/physique." }
    ],
    workouts: [
        { day: "Monday", focus: "Upper Body Strength (Push)", details: "Bench Press (4x8), Overhead Press (3x10), Triceps Extensions (3x12)" },
        { day: "Tuesday", focus: "Lower Body (Legs & Core)", details: "Squats (5x5), Deadlifts (3x8), Plank (3x60s)" },
        { day: "Wednesday", focus: "Active Recovery / Cardio", details: "30 min steady-state walk or swim." },
        { day: "Thursday", focus: "Upper Body Strength (Pull)", details: "Pull-ups (3xMax), Barbell Rows (4x10), Bicep Curls (3x12)" },
        { day: "Friday", focus: "Full Body Endurance", details: "Circuit training: KB Swings, Push-ups, Box Jumps (4 rounds)" },
        { day: "Saturday", focus: "Mobility & Stretch", details: "90 min Yoga or deep stretching routine." },
        { day: "Sunday", focus: "Rest", details: "Complete rest and meal prep." }
    ],
    disciplines: [
        { title: "Nutrition Discipline", agent: "The Spartan Chef", detail: "Prioritize 1g of protein per pound of bodyweight. Track calories daily for 6 days a week." },
        { title: "Mental Discipline", agent: "The Oracle Agent", detail: "Perform a 5-minute cold shower every morning to build resilience." },
    ]
};

// --- DOM Elements ---
const appRoot = document.getElementById('app-root');

// --- Render Functions ---

function render() {
    appRoot.innerHTML = '';

    // Logo
    appRoot.innerHTML += `
        <div class="flex items-center space-x-2 mb-8 justify-center">
            <i data-lucide="shield" class="w-8 h-8 ${PRIMARY_COLOR}"></i>
            <div class="text-xl font-extrabold tracking-tight">
                <span class="text-white">CADENCE</span><span class="${PRIMARY_COLOR} font-light">COACH</span>
            </div>
        </div>
    `;

    // Stepper (if not finished)
    if (state.page < 7) {
        renderStepper();
    }

    // Main Card
    const card = document.createElement('div');
    card.className = `p-6 sm:p-8 rounded-xl ${CARD_COLOR} shadow-2xl border border-gray-700`;

    // Page Content
    const content = renderPageContent();
    card.appendChild(content);

    // Navigation
    const nav = renderNavigation();
    card.appendChild(nav);

    // Error
    if (state.error) {
        const errDiv = document.createElement('div');
        errDiv.className = "text-red-400 text-sm mt-4 p-2 bg-red-900/50 rounded flex items-center";
        errDiv.innerHTML = `<i data-lucide="x-circle" class="w-4 h-4 mr-2"></i> ${state.error}`;
        card.appendChild(errDiv);
    }

    appRoot.appendChild(card);

    // Initialize Icons
    lucide.createIcons();
}

function renderStepper() {
    const steps = [
        { s: 1, t: "Start" },
        { s: 2, t: "Goal" },
        { s: 3, t: "Metrics" },
        { s: 4, t: "Context" },
        { s: 5, t: "Habits" },
        { s: 6, t: "Plan" },
        { s: 7, t: "Commit" },
    ];

    const stepperDiv = document.createElement('div');
    stepperDiv.className = "flex justify-between items-start mb-8 p-4 bg-gray-800 rounded-xl shadow-lg border border-gray-700";

    steps.forEach(step => {
        const active = step.s <= state.page;
        stepperDiv.innerHTML += `
            <div class="flex flex-col items-center space-y-1">
                <div class="w-8 h-8 flex items-center justify-center rounded-full text-sm font-bold transition-colors duration-300 ${active ? `${ACCENT_BG} text-gray-900` : 'bg-gray-700 text-gray-400'}">
                    ${step.s}
                </div>
                <span class="hidden sm:block text-xs font-medium text-center ${active ? 'text-white' : 'text-gray-500'}">${step.t}</span>
            </div>
        `;
    });

    appRoot.appendChild(stepperDiv);
}

function renderPageContent() {
    const container = document.createElement('div');
    container.className = "space-y-6";

    switch (state.page) {
        case 1:
            container.className = "text-center space-y-6";
            container.innerHTML = `
                <h2 class="text-3xl font-bold text-white mb-6">Welcome to Your Spartan Journey.</h2>
                <div class="grid md:grid-cols-2 gap-4">
                    <button onclick="handleNext()" class="flex flex-col items-center justify-center p-8 h-48 rounded-xl bg-gray-700 hover:bg-gray-600 transition duration-300 shadow-xl border border-gray-700">
                        <i data-lucide="user" class="w-8 h-8 ${PRIMARY_COLOR} mb-2"></i>
                        <span class="text-xl font-semibold text-white">New Recruit</span>
                        <span class="text-sm text-gray-400">Start from scratch and define your destiny.</span>
                    </button>
                    <button onclick="handleNext()" class="flex flex-col items-center justify-center p-8 h-48 rounded-xl bg-gray-700 hover:bg-gray-600 transition duration-300 shadow-xl border border-gray-700">
                        <i data-lucide="users" class="w-8 h-8 ${PRIMARY_COLOR} mb-2"></i>
                        <span class="text-xl font-semibold text-white">Veteran Return</span>
                        <span class="text-sm text-gray-400">Log in to continue your current campaign.</span>
                    </button>
                </div>
                <p class="text-sm text-gray-400 pt-4">Powered by the Angular Helmet Brand.</p>
            `;
            break;
        case 2:
            container.innerHTML = `
                <h2 class="text-2xl font-bold text-white border-b border-gray-700 pb-2 flex items-center"><i data-lucide="compass" class="w-5 h-5 mr-2 ${PRIMARY_COLOR}"></i> Define Your Mission</h2>
                ${renderInput('name', 'Your Name (Spartan Alias)', state.userData.name, 'Leonidas')}
                ${renderInput('fitnessGoal', 'Primary Fitness Goal', state.userData.fitnessGoal, 'Lose 15kg / Run a marathon')}
                ${renderInput('motivation', "The 'Why?' (Your Core Motivation)", state.userData.motivation, 'To live longer for my family')}
                ${renderInput('targetDate', 'Target Completion Date', state.userData.targetDate, '', 'date')}
            `;
            break;
        case 3:
            container.innerHTML = `
                <h2 class="text-2xl font-bold text-white border-b border-gray-700 pb-2 flex items-center"><i data-lucide="check-circle" class="w-5 h-5 mr-2 ${PRIMARY_COLOR}"></i> Baseline Metrics</h2>
                <div class="grid sm:grid-cols-2 gap-4">
                    ${renderInput('dob', 'Date of Birth (DOB)', state.userData.dob, '', 'date')}
                    ${renderInput('weight', 'Current Weight (kg)', state.userData.weight, '80', 'number')}
                </div>
                <div class="grid sm:grid-cols-2 gap-4">
                    ${renderInput('height', 'Height (cm)', state.userData.height, '175', 'number')}
                    <div class="space-y-1">
                        <label class="text-sm font-medium text-gray-300">Gender</label>
                        <select onchange="updateUserDataAndRender('gender', this.value)" class="w-full p-3 ${CARD_COLOR} border border-gray-700 rounded-lg focus:outline-none focus:ring-2 ${ACCENT_RING} text-white">
                            <option value="Male" ${state.userData.gender === 'Male' ? 'selected' : ''}>Male</option>
                            <option value="Female" ${state.userData.gender === 'Female' ? 'selected' : ''}>Female</option>
                            <option value="Other" ${state.userData.gender === 'Other' ? 'selected' : ''}>Other</option>
                        </select>
                    </div>
                </div>
            `;
            break;
        case 4:
            container.innerHTML = `
                <h2 class="text-2xl font-bold text-white border-b border-gray-700 pb-2 flex items-center"><i data-lucide="clock" class="w-5 h-5 mr-2 ${PRIMARY_COLOR}"></i> Environmental Constraints</h2>
                <div class="grid sm:grid-cols-2 gap-4">
                    ${renderInput('wakeTime', 'Usual Wake Hour', state.userData.wakeTime, '', 'time')}
                    ${renderInput('sleepTime', 'Usual Sleep Hour', state.userData.sleepTime, '', 'time')}
                </div>
                <div class="space-y-4">
                    <label class="text-sm font-medium text-gray-300 block">Workout Access</label>
                    <div class="grid grid-cols-3 gap-3">
                        ${renderRadio('access', 'Home', '🏠', 'Home Only')}
                        ${renderRadio('access', 'Gym', '🏋️', 'Gym Access')}
                        ${renderRadio('access', 'Mixed', '🔄', 'Mixed')}
                    </div>
                </div>
                <div class="space-y-4">
                    <label class="text-sm font-medium text-gray-300 block">Diet Type</label>
                    <div class="grid grid-cols-2 gap-3">
                        ${renderRadio('diet', 'Vegetarian', '🥦', 'Vegetarian')}
                        ${renderRadio('diet', 'Non-Vegetarian', '🥩', 'Non-Vegetarian')}
                    </div>
                </div>
            `;
            break;
        case 5:
            container.innerHTML = `
                <h2 class="text-2xl font-bold text-white border-b border-gray-700 pb-2 flex items-center"><i data-lucide="zap" class="w-5 h-5 mr-2 ${PRIMARY_COLOR}"></i> Micro-Habit Arsenal</h2>
                <p class="text-gray-400 text-sm">Select the small, powerful habits you want to integrate.</p>
                <div class="grid sm:grid-cols-2 gap-3">
                    ${microHabits.map(h => `
                        <button onclick="toggleStreak('${h.id}')" class="flex items-center justify-start p-3 rounded-lg transition duration-200 text-sm border ${state.userData.streaks.includes(h.id) ? `${ACCENT_BG} text-gray-900 font-semibold border-yellow-400` : 'bg-gray-700 hover:bg-gray-600 text-white border-gray-700'}">
                            <span class="mr-3 text-lg">${h.icon}</span>
                            ${h.name}
                        </button>
                    `).join('')}
                </div>
            `;
            break;
        case 6:
            if (state.loadingPlan) {
                container.innerHTML = `
                    <div class="flex flex-col items-center justify-center p-8">
                        <i data-lucide="refresh-cw" class="w-8 h-8 ${PRIMARY_COLOR} animate-spin"></i>
                        <p class="mt-4 text-gray-400">Running the Spartan Planner Agent...</p>
                    </div>
                `;
            } else if (state.plan) {
                container.innerHTML = `
                    <h2 class="text-3xl font-bold text-white text-center"><i data-lucide="dumbbell" class="w-6 h-6 inline mr-2 ${PRIMARY_COLOR}"></i> Your Forged 12-Week Plan</h2>
                    
                    <div class="bg-gray-700 p-5 rounded-xl border border-gray-600">
                        <h3 class="text-xl font-bold text-yellow-400 mb-3 flex items-center"><i data-lucide="award" class="w-5 h-5 mr-2"></i> Milestones</h3>
                        <ul class="space-y-3">
                            ${state.plan.milestones.map(m => `
                                <li class="p-3 bg-gray-800 rounded-lg border-l-4 border-yellow-400">
                                    <p class="font-semibold text-white">${m.title}</p>
                                    <p class="text-sm text-gray-400">${m.description}</p>
                                </li>
                            `).join('')}
                        </ul>
                    </div>

                    <div class="bg-gray-700 p-5 rounded-xl border border-gray-600">
                        <h3 class="text-xl font-bold text-yellow-400 mb-3 flex items-center"><i data-lucide="dumbbell" class="w-5 h-5 mr-2"></i> Workout Schedule</h3>
                        <div class="grid md:grid-cols-2 gap-4">
                            ${state.plan.workouts.slice(0, 4).map(w => `
                                <div class="p-3 bg-gray-800 rounded-lg">
                                    <p class="font-semibold text-white">${w.day}: ${w.focus}</p>
                                    <p class="text-xs text-gray-400">${w.details}</p>
                                </div>
                            `).join('')}
                        </div>
                    </div>

                    <div class="pt-4 space-y-4">
                        <div class="flex justify-end space-x-4">
                            <button onclick="setPage(7)" class="px-6 py-3 rounded-lg ${ACCENT_BG} text-gray-900 font-bold hover:bg-yellow-500 transition duration-300 w-full">
                                Accept Plan & Continue
                            </button>
                        </div>
                    </div>
                `;
            }
            break;
        case 7:
            container.innerHTML = `
                <h2 class="text-3xl font-bold text-white text-center mb-6">Commitment & Accountability</h2>
                <div class="bg-gray-700 p-5 rounded-xl border border-gray-600 space-y-4">
                    <h3 class="text-xl font-bold text-yellow-400 mb-2">Spartan Accountability</h3>
                    <p class="text-gray-300">Your journey is tracked by our *Spartan Agent* system.</p>
                </div>
                <button onclick="alert('Journey Accepted! Welcome to the CadenceCoach Spartan Program.')" class="w-full py-4 rounded-xl mt-6 ${ACCENT_BG} text-gray-900 text-xl font-bold uppercase tracking-wider shadow-lg hover:bg-yellow-500 transition duration-300">
                    Accept & Begin Your Journey
                </button>
            `;
            break;
    }
    return container;
}

function renderInput(id, label, value, placeholder, type = 'text') {
    return `
        <div class="space-y-1">
            <label for="${id}" class="text-sm font-medium text-gray-300 flex items-center">${label}</label>
            <input id="${id}" type="${type}" value="${value}" oninput="updateUserData('${id}', this.value)" placeholder="${placeholder}" class="w-full p-3 ${CARD_COLOR} border border-gray-700 rounded-lg focus:outline-none focus:ring-2 ${ACCENT_RING} text-white">
        </div>
    `;
}

function renderRadio(field, value, icon, label) {
    const selected = state.userData[field] === value;
    return `
        <button onclick="updateUserDataAndRender('${field}', '${value}')" class="w-full p-4 rounded-xl transition duration-300 shadow-md flex flex-col items-center space-y-2 text-sm ${selected ? `${ACCENT_BG} text-gray-900 font-semibold ring-4 ${ACCENT_RING}` : 'bg-gray-700 hover:bg-gray-600 text-white'}">
            <span class="text-2xl">${icon}</span>
            <span>${label}</span>
        </button>
    `;
}

function renderNavigation() {
    const div = document.createElement('div');
    div.className = "flex justify-between mt-8 pt-4 border-t border-gray-700";

    const backDisabled = state.page === 1 || state.page === 7 || state.loadingPlan;
    const nextDisabled = state.loadingPlan || !canGoNext();

    div.innerHTML = `
        <button onclick="handleBack()" ${backDisabled ? 'disabled' : ''} class="flex items-center px-4 py-2 rounded-lg transition duration-300 text-white ${backDisabled ? 'bg-gray-700 text-gray-500 cursor-not-allowed' : 'bg-gray-700 hover:bg-gray-600'}">
            <i data-lucide="chevron-left" class="w-5 h-5 mr-1"></i> Back
        </button>
    `;

    if (state.page < 6) {
        div.innerHTML += `
            <button id="next-btn" onclick="handleNext()" ${nextDisabled ? 'disabled' : ''} class="flex items-center px-6 py-2 rounded-lg transition duration-300 text-gray-900 font-semibold ${nextDisabled ? 'bg-gray-600 cursor-not-allowed' : `${ACCENT_BG} hover:bg-yellow-500`}">
                ${state.page === 5 ? (state.loadingPlan ? 'Forging Plan...' : 'Generate Plan') : 'Next Step'}
                <i data-lucide="chevron-right" class="w-5 h-5 ml-1"></i>
            </button>
        `;
    }

    return div;
}

// --- Logic ---

function updateUserData(field, value) {
    state.userData[field] = value;
    updateNavigationState();
}

function updateNavigationState() {
    const nextBtn = document.getElementById('next-btn');
    if (!nextBtn) return;

    if (canGoNext()) {
        nextBtn.disabled = false;
        nextBtn.classList.remove('bg-gray-600', 'cursor-not-allowed');
        nextBtn.classList.add('bg-yellow-400', 'hover:bg-yellow-500');
    } else {
        nextBtn.disabled = true;
        nextBtn.classList.add('bg-gray-600', 'cursor-not-allowed');
        nextBtn.classList.remove('bg-yellow-400', 'hover:bg-yellow-500');
    }
}

function updateUserDataAndRender(field, value) {
    state.userData[field] = value;
    render();
}

function toggleStreak(habitId) {
    const idx = state.userData.streaks.indexOf(habitId);
    if (idx === -1) {
        state.userData.streaks.push(habitId);
    } else {
        state.userData.streaks.splice(idx, 1);
    }
    render();
}

function canGoNext() {
    const d = state.userData;
    switch (state.page) {
        case 1: return true;
        case 2: return d.name && d.fitnessGoal && d.motivation && d.targetDate;
        case 3: return d.dob && d.weight && d.gender && d.height;
        case 4: return d.wakeTime && d.sleepTime && d.access && d.diet;
        case 5: return true;
        default: return true;
    }
}

function handleNext() {
    if (!canGoNext()) {
        state.error = 'Please fill in all required fields.';
        render();
        return;
    }
    state.error = '';

    if (state.page === 5) {
        generatePlan();
    } else if (state.page < 7) {
        state.page++;
        render();
    }
}

function handleBack() {
    if (state.page > 1) {
        state.page--;
        if (state.page === 6) state.plan = null;
        render();
    }
}

function setPage(p) {
    state.page = p;
    render();
}

function generatePlan() {
    state.loadingPlan = true;
    state.page = 6; // Move to loading screen
    render();

    setTimeout(() => {
        state.plan = mockPlan;
        state.loadingPlan = false;
        render();
    }, 2000);
}

// --- Init ---
render();
