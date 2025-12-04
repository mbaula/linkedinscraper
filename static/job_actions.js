var selectedJob = null;
var previewTimeout = null;
var currentPreviewJobId = null;
var focusedJobIndex = -1;
var visibleJobItems = [];

// Dark Mode Functions (Global - works across all pages)
function initDarkMode() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateDarkModeButton(savedTheme);
}

function toggleDarkMode() {
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateDarkModeButton(newTheme);
}

function updateDarkModeButton(theme) {
    const icon = document.getElementById('dark-mode-icon');
    const text = document.getElementById('dark-mode-text');
    if (icon && text) {
        if (theme === 'dark') {
            icon.textContent = '☀️';
            text.textContent = 'Light';
        } else {
            icon.textContent = '🌙';
            text.textContent = 'Dark';
        }
    }
}

// Initialize dark mode on page load (for all pages)
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDarkMode);
} else {
    initDarkMode();
}

// Job Preview Functions
let previewCache = {};

async function showJobPreview(event, jobId) {
    // Clear any existing timeout
    if (previewTimeout) {
        clearTimeout(previewTimeout);
    }
    
    // Don't show preview if already showing details for this job
    if (currentPreviewJobId === jobId) {
        return;
    }
    
    // Find the job item element
    const jobItem = document.querySelector(`.job-item[data-job-id="${jobId}"]`);
    if (!jobItem) return;
    
    // Set a small delay before showing preview
    previewTimeout = setTimeout(async function() {
        const previewCard = document.getElementById('job-preview-card');
        if (!previewCard) return;
        
        // Get job item position
        const rect = jobItem.getBoundingClientRect();
        
        // Position preview card to the right of the job item
        const cardWidth = 400;
        const cardHeight = 500;
        let left = rect.right + 20;
        let top = rect.top;
        
        // Adjust if card would go off screen to the right
        if (left + cardWidth > window.innerWidth - 20) {
            left = rect.left - cardWidth - 20;
        }
        // Adjust if card would go off screen to the left
        if (left < 20) {
            left = 20;
        }
        // Adjust vertical position
        if (top + cardHeight > window.innerHeight - 20) {
            top = window.innerHeight - cardHeight - 20;
        }
        if (top < 20) {
            top = 20;
        }
        
        previewCard.style.left = left + 'px';
        previewCard.style.top = top + 'px';
        
        // Check cache first
        if (previewCache[jobId]) {
            displayPreview(previewCache[jobId]);
            previewCard.classList.add('show');
            currentPreviewJobId = jobId;
            return;
        }
        
        // Fetch job details
        try {
            const response = await fetch('/job_details/' + jobId);
            const jobData = await response.json();
            
            // Cache the data
            previewCache[jobId] = jobData;
            
            // Display preview
            displayPreview(jobData);
            previewCard.classList.add('show');
            currentPreviewJobId = jobId;
        } catch (error) {
            console.error('Error fetching job preview:', error);
        }
    }, 500); // 500ms delay before showing preview
}

function displayPreview(jobData) {
    const previewCard = document.getElementById('job-preview-card');
    if (!previewCard) return;
    
    const titleEl = document.getElementById('preview-title');
    const companyEl = document.getElementById('preview-company');
    const locationEl = document.getElementById('preview-location');
    const dateEl = document.getElementById('preview-date');
    const descriptionEl = document.getElementById('preview-description');
    
    if (titleEl) titleEl.textContent = jobData.title || 'N/A';
    if (companyEl) companyEl.textContent = jobData.company || 'N/A';
    if (locationEl) locationEl.textContent = jobData.location || 'N/A';
    if (dateEl) dateEl.textContent = 'Posted: ' + (jobData.date || 'N/A');
    
    if (descriptionEl) {
        const description = jobData.job_description || '';
        // Limit description to first 500 characters
        const truncated = description.length > 500 ? description.substring(0, 500) : description;
        descriptionEl.textContent = truncated;
    }
}

function hideJobPreview() {
    if (previewTimeout) {
        clearTimeout(previewTimeout);
        previewTimeout = null;
    }
    
    const previewCard = document.getElementById('job-preview-card');
    if (previewCard) {
        previewCard.classList.remove('show');
    }
    currentPreviewJobId = null;
}

function setupJobPreviewHover() {
    // Add hover event listeners to all job items
    const jobItems = document.querySelectorAll('.job-item');
    jobItems.forEach(function(jobItem) {
        const jobId = jobItem.getAttribute('data-job-id');
        if (jobId && !jobItem.hasAttribute('data-preview-setup')) {
            // Mark as set up to avoid duplicate listeners
            jobItem.setAttribute('data-preview-setup', 'true');
            
            jobItem.addEventListener('mouseenter', function(event) {
                showJobPreview(event, jobId);
            });
            
            jobItem.addEventListener('mouseleave', function(event) {
                // Only hide if not moving to preview card
                const relatedTarget = event.relatedTarget;
                const previewCard = document.getElementById('job-preview-card');
                if (!relatedTarget || (relatedTarget !== previewCard && !previewCard.contains(relatedTarget))) {
                    hideJobPreview();
                }
            });
            
            // Clear keyboard focus when clicking with mouse
            jobItem.addEventListener('click', function() {
                updateVisibleJobsList();
                const jobIndex = visibleJobItems.indexOf(jobItem);
                if (jobIndex >= 0) {
                    focusedJobIndex = jobIndex;
                    // Remove focus class from all jobs
                    visibleJobItems.forEach(function(item) {
                        item.classList.remove('job-item-focused');
                    });
                    jobItem.classList.add('job-item-focused');
                }
            });
        }
    });
    
    // Keep preview visible when hovering over it
    const previewCard = document.getElementById('job-preview-card');
    if (previewCard) {
        previewCard.addEventListener('mouseenter', function() {
            // Keep preview visible
        });
        
        previewCard.addEventListener('mouseleave', function() {
            hideJobPreview();
        });
    }
}

// Keyboard Navigation Functions
function setupKeyboardNavigation() {
    document.addEventListener('keydown', function(event) {
        // Don't handle keyboard shortcuts when user is typing in inputs, textareas, or contenteditable elements
        const activeElement = document.activeElement;
        const isInputFocused = activeElement && (
            activeElement.tagName === 'INPUT' ||
            activeElement.tagName === 'TEXTAREA' ||
            activeElement.isContentEditable ||
            activeElement.tagName === 'SELECT'
        );
        
        // Escape key - close modals/previews
        if (event.key === 'Escape') {
            hideJobPreview();
            closeAllDropdowns();
            // Close any open modals
            const coverLetterModal = document.getElementById('cover-letter-modal');
            const latexModal = document.getElementById('latex-modal');
            const analysisModal = document.getElementById('analysis-modal');
            const analysisHistoryModal = document.getElementById('analysis-history-modal');
            
            if (coverLetterModal && coverLetterModal.style.display === 'block') {
                closeCoverLetterFullscreen();
            }
            if (latexModal && latexModal.style.display === 'block') {
                closeLatexModal();
            }
            if (analysisModal && analysisModal.style.display === 'block') {
                closeAnalysisModal();
            }
            if (analysisHistoryModal && analysisHistoryModal.style.display === 'block') {
                closeAnalysisHistoryModal();
            }
            return;
        }
        
        // If user is typing in an input, only handle Escape
        if (isInputFocused && event.key !== 'Escape') {
            return;
        }
        
        // Update visible jobs list before navigation
        updateVisibleJobsList();
        
        // Arrow keys - navigate jobs
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault();
            navigateJobs(event.key === 'ArrowDown' ? 1 : -1);
            return;
        }
        
        // Enter or Space - view job details
        if (event.key === 'Enter' || event.key === ' ') {
            if (focusedJobIndex >= 0 && focusedJobIndex < visibleJobItems.length) {
                event.preventDefault();
                const jobId = visibleJobItems[focusedJobIndex].getAttribute('data-job-id');
                if (jobId) {
                    showJobDetails(jobId);
                }
            }
            return;
        }
        
        // Keyboard shortcuts (only when not typing)
        if (!isInputFocused) {
            // '/' or '?' - Focus search bar or show help
            if ((event.key === '/' || event.key === '?') && !event.ctrlKey && !event.metaKey && !event.altKey) {
                event.preventDefault();
                if (event.key === '?') {
                    toggleKeyboardHelp();
                } else {
                    const searchBar = document.getElementById('search-bar');
                    if (searchBar) {
                        searchBar.focus();
                        searchBar.select();
                    }
                }
                return;
            }
        }
    });
    
    // Update visible jobs list on initial load
    setTimeout(updateVisibleJobsList, 500);
}

function navigateJobs(direction) {
    if (visibleJobItems.length === 0) {
        focusedJobIndex = -1;
        return;
    }
    
    // Remove previous focus
    if (focusedJobIndex >= 0 && focusedJobIndex < visibleJobItems.length) {
        visibleJobItems[focusedJobIndex].classList.remove('job-item-focused');
    }
    
    // Calculate new index
    if (focusedJobIndex === -1) {
        // Start from first or last job
        focusedJobIndex = direction > 0 ? 0 : visibleJobItems.length - 1;
    } else {
        focusedJobIndex += direction;
        // Wrap around
        if (focusedJobIndex < 0) {
            focusedJobIndex = visibleJobItems.length - 1;
        } else if (focusedJobIndex >= visibleJobItems.length) {
            focusedJobIndex = 0;
        }
    }
    
    // Apply focus to new job
    if (focusedJobIndex >= 0 && focusedJobIndex < visibleJobItems.length) {
        const focusedJob = visibleJobItems[focusedJobIndex];
        focusedJob.classList.add('job-item-focused');
        
        // Scroll into view
        focusedJob.scrollIntoView({
            behavior: 'smooth',
            block: 'nearest'
        });
        
        // Show preview after a short delay
        const jobId = focusedJob.getAttribute('data-job-id');
        if (jobId) {
            setTimeout(function() {
                // Create a synthetic event for preview
                const syntheticEvent = {
                    currentTarget: focusedJob
                };
                showJobPreview(syntheticEvent, jobId);
            }, 300);
        }
    }
}

function updateVisibleJobsList() {
    // Get all visible (not hidden) job items
    const allJobItems = document.querySelectorAll('.job-item');
    visibleJobItems = Array.from(allJobItems).filter(function(jobItem) {
        return !jobItem.classList.contains('hidden');
    });
    
    // Reset focused index if current focus is out of bounds
    if (focusedJobIndex >= visibleJobItems.length) {
        focusedJobIndex = -1;
    }
}

// Standard country list with ISO codes
const COUNTRIES = [
    {code: 'AF', name: 'Afghanistan'}, {code: 'AX', name: 'Åland Islands'}, {code: 'AL', name: 'Albania'},
    {code: 'DZ', name: 'Algeria'}, {code: 'AS', name: 'American Samoa'}, {code: 'AD', name: 'Andorra'},
    {code: 'AO', name: 'Angola'}, {code: 'AI', name: 'Anguilla'}, {code: 'AQ', name: 'Antarctica'},
    {code: 'AG', name: 'Antigua and Barbuda'}, {code: 'AR', name: 'Argentina'}, {code: 'AM', name: 'Armenia'},
    {code: 'AW', name: 'Aruba'}, {code: 'AU', name: 'Australia'}, {code: 'AT', name: 'Austria'},
    {code: 'AZ', name: 'Azerbaijan'}, {code: 'BS', name: 'Bahamas'}, {code: 'BH', name: 'Bahrain'},
    {code: 'BD', name: 'Bangladesh'}, {code: 'BB', name: 'Barbados'}, {code: 'BY', name: 'Belarus'},
    {code: 'BE', name: 'Belgium'}, {code: 'BZ', name: 'Belize'}, {code: 'BJ', name: 'Benin'},
    {code: 'BM', name: 'Bermuda'}, {code: 'BT', name: 'Bhutan'}, {code: 'BO', name: 'Bolivia (Plurinational State of)'},
    {code: 'BA', name: 'Bosnia and Herzegovina'}, {code: 'BW', name: 'Botswana'}, {code: 'BV', name: 'Bouvet Island'},
    {code: 'BR', name: 'Brazil'}, {code: 'IO', name: 'British Indian Ocean Territory'}, {code: 'BN', name: 'Brunei Darussalam'},
    {code: 'BG', name: 'Bulgaria'}, {code: 'BF', name: 'Burkina Faso'}, {code: 'BI', name: 'Burundi'},
    {code: 'CV', name: 'Cabo Verde'}, {code: 'KH', name: 'Cambodia'}, {code: 'CM', name: 'Cameroon'},
    {code: 'CA', name: 'Canada'}, {code: 'BQ', name: 'Caribbean Netherlands'}, {code: 'KY', name: 'Cayman Islands'},
    {code: 'CF', name: 'Central African Republic'}, {code: 'TD', name: 'Chad'}, {code: 'CL', name: 'Chile'},
    {code: 'CN', name: 'China'}, {code: 'CX', name: 'Christmas Island'}, {code: 'CC', name: 'Cocos (Keeling) Islands'},
    {code: 'CO', name: 'Colombia'}, {code: 'KM', name: 'Comoros'}, {code: 'CG', name: 'Congo'},
    {code: 'CD', name: 'Congo, Democratic Republic of the'}, {code: 'CK', name: 'Cook Islands'}, {code: 'CR', name: 'Costa Rica'},
    {code: 'HR', name: 'Croatia'}, {code: 'CU', name: 'Cuba'}, {code: 'CW', name: 'Curaçao'},
    {code: 'CY', name: 'Cyprus'}, {code: 'CZ', name: 'Czech Republic'}, {code: 'CI', name: "Côte d'Ivoire"},
    {code: 'DK', name: 'Denmark'}, {code: 'DJ', name: 'Djibouti'}, {code: 'DM', name: 'Dominica'},
    {code: 'DO', name: 'Dominican Republic'}, {code: 'EC', name: 'Ecuador'}, {code: 'EG', name: 'Egypt'},
    {code: 'SV', name: 'El Salvador'}, {code: 'GQ', name: 'Equatorial Guinea'}, {code: 'ER', name: 'Eritrea'},
    {code: 'EE', name: 'Estonia'}, {code: 'SZ', name: 'Eswatini (Swaziland)'}, {code: 'ET', name: 'Ethiopia'},
    {code: 'FK', name: 'Falkland Islands (Malvinas)'}, {code: 'FO', name: 'Faroe Islands'}, {code: 'FJ', name: 'Fiji'},
    {code: 'FI', name: 'Finland'}, {code: 'FR', name: 'France'}, {code: 'GF', name: 'French Guiana'},
    {code: 'PF', name: 'French Polynesia'}, {code: 'TF', name: 'French Southern Territories'}, {code: 'GA', name: 'Gabon'},
    {code: 'GM', name: 'Gambia'}, {code: 'GE', name: 'Georgia'}, {code: 'DE', name: 'Germany'},
    {code: 'GH', name: 'Ghana'}, {code: 'GI', name: 'Gibraltar'}, {code: 'GR', name: 'Greece'},
    {code: 'GL', name: 'Greenland'}, {code: 'GD', name: 'Grenada'}, {code: 'GP', name: 'Guadeloupe'},
    {code: 'GU', name: 'Guam'}, {code: 'GT', name: 'Guatemala'}, {code: 'GG', name: 'Guernsey'},
    {code: 'GN', name: 'Guinea'}, {code: 'GW', name: 'Guinea-Bissau'}, {code: 'GY', name: 'Guyana'},
    {code: 'HT', name: 'Haiti'}, {code: 'HM', name: 'Heard Island and Mcdonald Islands'}, {code: 'HN', name: 'Honduras'},
    {code: 'HK', name: 'Hong Kong'}, {code: 'HU', name: 'Hungary'}, {code: 'IS', name: 'Iceland'},
    {code: 'IN', name: 'India'}, {code: 'ID', name: 'Indonesia'}, {code: 'IR', name: 'Iran'},
    {code: 'IQ', name: 'Iraq'}, {code: 'IE', name: 'Ireland'}, {code: 'IM', name: 'Isle of Man'},
    {code: 'IL', name: 'Israel'}, {code: 'IT', name: 'Italy'}, {code: 'JM', name: 'Jamaica'},
    {code: 'JP', name: 'Japan'}, {code: 'JE', name: 'Jersey'}, {code: 'JO', name: 'Jordan'},
    {code: 'KZ', name: 'Kazakhstan'}, {code: 'KE', name: 'Kenya'}, {code: 'KI', name: 'Kiribati'},
    {code: 'KP', name: 'Korea, North'}, {code: 'KR', name: 'Korea, South'}, {code: 'XK', name: 'Kosovo'},
    {code: 'KW', name: 'Kuwait'}, {code: 'KG', name: 'Kyrgyzstan'}, {code: 'LA', name: 'Lao People\'s Democratic Republic'},
    {code: 'LV', name: 'Latvia'}, {code: 'LB', name: 'Lebanon'}, {code: 'LS', name: 'Lesotho'},
    {code: 'LR', name: 'Liberia'}, {code: 'LY', name: 'Libya'}, {code: 'LI', name: 'Liechtenstein'},
    {code: 'LT', name: 'Lithuania'}, {code: 'LU', name: 'Luxembourg'}, {code: 'MO', name: 'Macao'},
    {code: 'MK', name: 'Macedonia North'}, {code: 'MG', name: 'Madagascar'}, {code: 'MW', name: 'Malawi'},
    {code: 'MY', name: 'Malaysia'}, {code: 'MV', name: 'Maldives'}, {code: 'ML', name: 'Mali'},
    {code: 'MT', name: 'Malta'}, {code: 'MH', name: 'Marshall Islands'}, {code: 'MQ', name: 'Martinique'},
    {code: 'MR', name: 'Mauritania'}, {code: 'MU', name: 'Mauritius'}, {code: 'YT', name: 'Mayotte'},
    {code: 'MX', name: 'Mexico'}, {code: 'FM', name: 'Micronesia'}, {code: 'MD', name: 'Moldova'},
    {code: 'MC', name: 'Monaco'}, {code: 'MN', name: 'Mongolia'}, {code: 'ME', name: 'Montenegro'},
    {code: 'MS', name: 'Montserrat'}, {code: 'MA', name: 'Morocco'}, {code: 'MZ', name: 'Mozambique'},
    {code: 'MM', name: 'Myanmar (Burma)'}, {code: 'NA', name: 'Namibia'}, {code: 'NR', name: 'Nauru'},
    {code: 'NP', name: 'Nepal'}, {code: 'NL', name: 'Netherlands'}, {code: 'AN', name: 'Netherlands Antilles'},
    {code: 'NC', name: 'New Caledonia'}, {code: 'NZ', name: 'New Zealand'}, {code: 'NI', name: 'Nicaragua'},
    {code: 'NE', name: 'Niger'}, {code: 'NG', name: 'Nigeria'}, {code: 'NU', name: 'Niue'},
    {code: 'NF', name: 'Norfolk Island'}, {code: 'MP', name: 'Northern Mariana Islands'}, {code: 'NO', name: 'Norway'},
    {code: 'OM', name: 'Oman'}, {code: 'PK', name: 'Pakistan'}, {code: 'PW', name: 'Palau'},
    {code: 'PS', name: 'Palestine'}, {code: 'PA', name: 'Panama'}, {code: 'PG', name: 'Papua New Guinea'},
    {code: 'PY', name: 'Paraguay'}, {code: 'PE', name: 'Peru'}, {code: 'PH', name: 'Philippines'},
    {code: 'PN', name: 'Pitcairn Islands'}, {code: 'PL', name: 'Poland'}, {code: 'PT', name: 'Portugal'},
    {code: 'PR', name: 'Puerto Rico'}, {code: 'QA', name: 'Qatar'}, {code: 'RE', name: 'Reunion'},
    {code: 'RO', name: 'Romania'}, {code: 'RU', name: 'Russian Federation'}, {code: 'RW', name: 'Rwanda'},
    {code: 'BL', name: 'Saint Barthelemy'}, {code: 'SH', name: 'Saint Helena'}, {code: 'KN', name: 'Saint Kitts and Nevis'},
    {code: 'LC', name: 'Saint Lucia'}, {code: 'MF', name: 'Saint Martin'}, {code: 'PM', name: 'Saint Pierre and Miquelon'},
    {code: 'VC', name: 'Saint Vincent and the Grenadines'}, {code: 'WS', name: 'Samoa'}, {code: 'SM', name: 'San Marino'},
    {code: 'ST', name: 'Sao Tome and Principe'}, {code: 'SA', name: 'Saudi Arabia'}, {code: 'SN', name: 'Senegal'},
    {code: 'RS', name: 'Serbia'}, {code: 'CS', name: 'Serbia and Montenegro'}, {code: 'SC', name: 'Seychelles'},
    {code: 'SL', name: 'Sierra Leone'}, {code: 'SG', name: 'Singapore'}, {code: 'SX', name: 'Sint Maarten'},
    {code: 'SK', name: 'Slovakia'}, {code: 'SI', name: 'Slovenia'}, {code: 'SB', name: 'Solomon Islands'},
    {code: 'SO', name: 'Somalia'}, {code: 'ZA', name: 'South Africa'}, {code: 'GS', name: 'South Georgia and the South Sandwich Islands'},
    {code: 'SS', name: 'South Sudan'}, {code: 'ES', name: 'Spain'}, {code: 'LK', name: 'Sri Lanka'},
    {code: 'SD', name: 'Sudan'}, {code: 'SR', name: 'Suriname'}, {code: 'SJ', name: 'Svalbard and Jan Mayen'},
    {code: 'SE', name: 'Sweden'}, {code: 'CH', name: 'Switzerland'}, {code: 'SY', name: 'Syria'},
    {code: 'TW', name: 'Taiwan'}, {code: 'TJ', name: 'Tajikistan'}, {code: 'TZ', name: 'Tanzania'},
    {code: 'TH', name: 'Thailand'}, {code: 'TL', name: 'Timor-Leste'}, {code: 'TG', name: 'Togo'},
    {code: 'TK', name: 'Tokelau'}, {code: 'TO', name: 'Tonga'}, {code: 'TT', name: 'Trinidad and Tobago'},
    {code: 'TN', name: 'Tunisia'}, {code: 'TR', name: 'Turkey (Türkiye)'}, {code: 'TM', name: 'Turkmenistan'},
    {code: 'TC', name: 'Turks and Caicos Islands'}, {code: 'TV', name: 'Tuvalu'}, {code: 'UM', name: 'U.S. Outlying Islands'},
    {code: 'UG', name: 'Uganda'}, {code: 'UA', name: 'Ukraine'}, {code: 'AE', name: 'United Arab Emirates'},
    {code: 'GB', name: 'United Kingdom'}, {code: 'US', name: 'United States'}, {code: 'UY', name: 'Uruguay'},
    {code: 'UZ', name: 'Uzbekistan'}, {code: 'VU', name: 'Vanuatu'}, {code: 'VA', name: 'Vatican City Holy See'},
    {code: 'VE', name: 'Venezuela'}, {code: 'VN', name: 'Vietnam'}, {code: 'VG', name: 'Virgin Islands, British'},
    {code: 'VI', name: 'Virgin Islands, U.S'}, {code: 'WF', name: 'Wallis and Futuna'}, {code: 'EH', name: 'Western Sahara'},
    {code: 'YE', name: 'Yemen'}, {code: 'ZM', name: 'Zambia'}, {code: 'ZW', name: 'Zimbabwe'}
];

// Multi-select filter state
let selectedFilters = {
    city: [],
    title: [],
    company: [],
    country: [],
    status: []
};

// Save filters to localStorage
function saveFiltersToStorage() {
    try {
        const filterState = {
            selectedFilters: selectedFilters,
            searchBar: document.getElementById('search-bar') ? document.getElementById('search-bar').value : '',
            sortBy: document.getElementById('sort-by') ? document.getElementById('sort-by').value : '',
            dateFilter: document.getElementById('filter-date') ? document.getElementById('filter-date').value : ''
        };
        localStorage.setItem('jobListFilters', JSON.stringify(filterState));
    } catch (e) {
        console.error('Error saving filters to localStorage:', e);
    }
}

// Load filters from localStorage
function loadFiltersFromStorage() {
    try {
        const saved = localStorage.getItem('jobListFilters');
        if (saved) {
            return JSON.parse(saved);
        }
    } catch (e) {
        console.error('Error loading filters from localStorage:', e);
    }
    return null;
}

// Search and filter functionality
document.addEventListener('DOMContentLoaded', function() {
    // Initialize dark mode
    initDarkMode();
    
    // Set up job preview hover events
    setupJobPreviewHover();
    
    // Set up keyboard navigation
    setupKeyboardNavigation();
    
    // Re-setup hover events after filters are applied (jobs might be reordered)
    // Hook into sortJobs function to re-setup hover after sorting
    const originalSortJobs = sortJobs;
    sortJobs = function(jobItems, sortOption) {
        const result = originalSortJobs.apply(this, arguments);
        // Re-setup hover after a short delay to allow DOM updates
        setTimeout(setupJobPreviewHover, 50);
        // Update visible jobs list for keyboard navigation
        updateVisibleJobsList();
        return result;
    };
    
    const searchBar = document.getElementById('search-bar');
    const sortBy = document.getElementById('sort-by');
    const filterDate = document.getElementById('filter-date');
    
    // Check if we should show hidden jobs (from URL parameter)
    const urlParams = new URLSearchParams(window.location.search);
    const includeHidden = urlParams.get('include_hidden') === 'true';
    
    // Load saved filters from localStorage (if no URL params)
    const savedFilters = loadFiltersFromStorage();
    const hasUrlParams = urlParams.has('status_filters') || urlParams.has('city_filters') || 
                         urlParams.has('title_filters') || urlParams.has('company_filters') || 
                         urlParams.has('country_filters');
    
    // Restore filter states from URL if they exist, otherwise use localStorage
    const statusFilters = urlParams.get('status_filters');
    if (statusFilters) {
        selectedFilters.status = statusFilters.split(',').filter(f => f);
        // Update checkboxes
        selectedFilters.status.forEach(function(status) {
            const checkbox = document.getElementById(`filter-status-${status}`);
            if (checkbox) {
                checkbox.checked = true;
            }
        });
        updateFilterDisplay('status');
    } else if (includeHidden) {
        // Legacy: if include_hidden is true but no status_filters, just add hidden
        selectedFilters.status.push('hidden');
        const hiddenCheckbox = document.getElementById('filter-status-hidden');
        if (hiddenCheckbox) {
            hiddenCheckbox.checked = true;
        }
        updateFilterDisplay('status');
    } else if (savedFilters && savedFilters.selectedFilters && savedFilters.selectedFilters.status && savedFilters.selectedFilters.status.length > 0) {
        // Restore from localStorage
        selectedFilters.status = savedFilters.selectedFilters.status || [];
        // Note: Checkboxes will be updated after DOM is ready
    }
    
    // Restore other filters from URL (after populateFilters runs), or from localStorage
    const cityFilters = urlParams.get('city_filters');
    const titleFilters = urlParams.get('title_filters');
    const companyFilters = urlParams.get('company_filters');
    const countryFilters = urlParams.get('country_filters');
    
    // Store for later restoration after populateFilters
    const filtersToRestore = {
        city: cityFilters ? cityFilters.split(',').filter(f => f) : (savedFilters && savedFilters.selectedFilters && savedFilters.selectedFilters.city ? savedFilters.selectedFilters.city : []),
        title: titleFilters ? titleFilters.split(',').filter(f => f) : (savedFilters && savedFilters.selectedFilters && savedFilters.selectedFilters.title ? savedFilters.selectedFilters.title : []),
        company: companyFilters ? companyFilters.split(',').filter(f => f) : (savedFilters && savedFilters.selectedFilters && savedFilters.selectedFilters.company ? savedFilters.selectedFilters.company : []),
        country: countryFilters ? countryFilters.split(',').filter(f => f) : (savedFilters && savedFilters.selectedFilters && savedFilters.selectedFilters.country ? savedFilters.selectedFilters.country : [])
    };
    
    // Restore search bar, sort, and date filter from localStorage if no URL params
    if (!hasUrlParams && savedFilters) {
        if (searchBar && savedFilters.searchBar) {
            searchBar.value = savedFilters.searchBar;
        }
        if (sortBy && savedFilters.sortBy) {
            sortBy.value = savedFilters.sortBy;
        }
        if (filterDate && savedFilters.dateFilter) {
            filterDate.value = savedFilters.dateFilter;
        }
    }
    
    // Check if search was completed and refresh if needed
    checkForSearchCompletion();
    
    // Populate filter dropdowns with unique values
    populateFilters();
    
    // Restore filters after they're populated
    setTimeout(function() {
        // Restore status filter checkboxes (they exist in DOM, just need to be checked)
        if (savedFilters && savedFilters.selectedFilters && savedFilters.selectedFilters.status && savedFilters.selectedFilters.status.length > 0) {
            selectedFilters.status.forEach(function(status) {
                const checkbox = document.getElementById(`filter-status-${status}`);
                if (checkbox) {
                    checkbox.checked = true;
                }
            });
            updateFilterDisplay('status');
        }
        
        // Restore other filters (city, title, company, country)
        Object.keys(filtersToRestore).forEach(function(type) {
            if (filtersToRestore[type].length > 0) {
                selectedFilters[type] = filtersToRestore[type];
                // Update checkboxes
                filtersToRestore[type].forEach(function(value) {
                    const optionsContainer = document.getElementById(`${type}-options`);
                    if (optionsContainer) {
                        const checkboxes = optionsContainer.querySelectorAll('input[type="checkbox"]');
                        for (let i = 0; i < checkboxes.length; i++) {
                            const checkboxValue = checkboxes[i].value.replace(/&quot;/g, '"').replace(/&#39;/g, "'");
                            if (checkboxValue === value) {
                                checkboxes[i].checked = true;
                                break;
                            }
                        }
                    }
                });
                updateFilterDisplay(type);
            }
        });
        
        // Apply filters after all filters are restored (especially important if hidden filter is active)
        applyAllFilters();
        // Save filters to localStorage after they're applied (so URL params get saved too)
        saveFiltersToStorage();
    }, 300);
    
    // Add event listeners
    if (searchBar) {
        searchBar.addEventListener('input', function() {
            applyAllFilters();
            saveFiltersToStorage();
        });
    }
    if (sortBy) {
        sortBy.addEventListener('change', function() {
            applyAllFilters();
            saveFiltersToStorage();
        });
    }
    if (filterDate) {
        filterDate.addEventListener('change', function() {
            applyAllFilters();
            saveFiltersToStorage();
        });
    }
    
    // Close dropdowns when clicking outside
    document.addEventListener('click', function(event) {
        if (!event.target.closest('.multi-select')) {
            closeAllDropdowns();
        }
    });
    
    // Check for search completion periodically and on visibility change
    setInterval(checkForSearchCompletion, 3000);
    document.addEventListener('visibilitychange', function() {
        if (!document.hidden) {
            checkForSearchCompletion();
        }
    });
});

function checkForSearchCompletion() {
    const refreshFlag = localStorage.getItem('refreshJobsList');
    if (refreshFlag === 'true') {
        // Clear the flag
        localStorage.removeItem('refreshJobsList');
        const completedAt = localStorage.getItem('searchCompleted');
        localStorage.removeItem('searchCompleted');
        
        // Auto-refresh to show new jobs
        // Show a brief message if possible, then refresh
        const notification = document.createElement('div');
        notification.style.cssText = 'position: fixed; top: 20px; right: 20px; background: #4CAF50; color: white; padding: 15px 20px; border-radius: 5px; z-index: 10000; box-shadow: 0 4px 8px rgba(0,0,0,0.2);';
        notification.textContent = 'Search completed! Refreshing jobs list...';
        document.body.appendChild(notification);
        
        // Refresh after a brief delay to show the message
        setTimeout(function() {
            window.location.reload();
        }, 1500);
    }
}

// Function to match location to country name from standard list
function extractCountry(location) {
    // Extract country from location string by matching against standard country list
    if (!location) return '';
    
    const locationLower = location.toLowerCase();
    
    // Handle special cases for metropolitan areas and regions first
    if (locationLower.includes('greater montreal') || locationLower.includes('montreal') || 
        locationLower.includes('greater vancouver') || locationLower.includes('vancouver') ||
        locationLower.includes('greater toronto') || locationLower.includes('gta') ||
        locationLower.includes('ottawa') || locationLower.includes('calgary') ||
        locationLower.includes('edmonton') || locationLower.includes('winnipeg')) {
        return 'Canada';
    }
    
    const parts = location.split(',').map(p => p.trim());
    
    // US state abbreviations (2 letters) - if found, it's US
    const usStates = ['AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA', 
                      'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD', 
                      'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ', 
                      'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 
                      'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY'];
    
    // Check if any part matches a US state
    for (const part of parts) {
        if (usStates.includes(part.toUpperCase())) {
            return 'United States';
        }
    }
    
    // Canadian provinces (2 letters and full names)
    const canadianProvinces = ['AB', 'BC', 'MB', 'NB', 'NL', 'NS', 'NT', 'NU', 'ON', 'PE', 'QC', 'SK', 'YT'];
    const canadianProvinceNames = ['ontario', 'quebec', 'british columbia', 'alberta', 'manitoba', 
                                   'saskatchewan', 'nova scotia', 'new brunswick', 'newfoundland', 
                                   'prince edward island', 'northwest territories', 'yukon', 'nunavut'];
    
    // Check for Canadian provinces
    for (const part of parts) {
        const partUpper = part.toUpperCase();
        const partLower = part.toLowerCase();
        if (canadianProvinces.includes(partUpper) || canadianProvinceNames.some(name => partLower.includes(name))) {
            return 'Canada';
        }
    }
    
    // Try to match against country names from standard list (case-insensitive)
    // Check each part of the location against country names
    for (const part of parts) {
        const partLower = part.toLowerCase();
        
        // Try exact match first
        for (const country of COUNTRIES) {
            const countryNameLower = country.name.toLowerCase();
            if (partLower === countryNameLower || partLower === country.code.toLowerCase()) {
                return country.name;
            }
        }
        
        // Try partial match (location contains country name or vice versa)
        for (const country of COUNTRIES) {
            const countryNameLower = country.name.toLowerCase();
            if (partLower.includes(countryNameLower) || countryNameLower.includes(partLower)) {
                return country.name;
            }
        }
        
        // Check common variations
        if (partLower.includes('united states') || partLower.includes('usa') || partLower === 'us' || partLower === 'u.s.') {
            return 'United States';
        }
        if (partLower.includes('united kingdom') || partLower === 'uk' || partLower === 'u.k.' || partLower === 'great britain') {
            return 'United Kingdom';
        }
    }
    
    // If no match found, return empty string (let the filter handle it)
    return '';
}

function populateFilters() {
    const jobItems = document.querySelectorAll('.job-item');
    const cities = new Set();
    const titles = new Set();
    const companies = new Set();
    const countries = new Set();
    
    jobItems.forEach(function(jobItem) {
        const city = jobItem.getAttribute('data-city');
        const title = jobItem.getAttribute('data-title');
        const company = jobItem.getAttribute('data-company');
        const location = jobItem.getAttribute('data-city'); // location is stored in data-city
        
        if (city) cities.add(city);
        if (title) titles.add(title);
        if (company) companies.add(company);
        
        // Extract country from location
        const country = extractCountry(location);
        if (country) countries.add(country);
    });
    
    // Populate city filter
    populateMultiSelect('city', Array.from(cities).sort());
    
    // Populate title filter
    populateMultiSelect('title', Array.from(titles).sort());
    
    // Populate company filter
    populateMultiSelect('company', Array.from(companies).sort());
    
    // Populate country filter with standard country list
    const countryNames = COUNTRIES.map(c => c.name).sort();
    populateMultiSelect('country', countryNames);
}

function populateMultiSelect(type, options) {
    const optionsContainer = document.getElementById(`${type}-options`);
    optionsContainer.innerHTML = '';
    
    // Separate selected and unselected options
    const selectedOptions = [];
    const unselectedOptions = [];
    
    options.forEach(function(option) {
        const isSelected = selectedFilters[type].includes(option);
        if (isSelected) {
            selectedOptions.push(option);
        } else {
            unselectedOptions.push(option);
        }
    });
    
    // Sort each group
    selectedOptions.sort();
    unselectedOptions.sort();
    
    // Function to create option element
    function createOptionElement(option) {
        const div = document.createElement('div');
        div.className = 'multi-select-option';
        const safeId = `${type}-${option.replace(/[^a-zA-Z0-9]/g, '_')}_${Math.random().toString(36).substr(2, 9)}`;
        const escapedValue = option.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
        const isSelected = selectedFilters[type].includes(option);
        
        if (isSelected) {
            div.classList.add('selected');
        }
        
        div.innerHTML = `
            <input type="checkbox" id="${safeId}" value="${escapedValue}" onchange="toggleFilter('${type}', this.value, event)"${isSelected ? ' checked' : ''}>
            <label for="${safeId}" style="cursor: pointer; flex: 1;" onclick="event.preventDefault(); document.getElementById('${safeId}').click();">${option}</label>
        `;
        return div;
    }
    
    // Append selected options first
    selectedOptions.forEach(function(option) {
        optionsContainer.appendChild(createOptionElement(option));
    });
    
    // Append unselected options after
    unselectedOptions.forEach(function(option) {
        optionsContainer.appendChild(createOptionElement(option));
    });
}


function toggleImprovements(improvementsId) {
    const improvementsDiv = document.getElementById(improvementsId);
    const arrow = document.getElementById(improvementsId + '-arrow');
    if (improvementsDiv && arrow) {
        if (improvementsDiv.style.display === 'none') {
            improvementsDiv.style.display = 'block';
            arrow.textContent = '▲';
        } else {
            improvementsDiv.style.display = 'none';
            arrow.textContent = '▼';
        }
    }
}

function toggleStepResult(resultId, arrowId) {
    const resultDiv = document.getElementById(resultId);
    const arrow = document.getElementById(arrowId);
    if (resultDiv && arrow) {
        if (resultDiv.style.display === 'none' || resultDiv.style.display === '') {
            resultDiv.style.display = 'block';
            resultDiv.classList.add('show');
            arrow.textContent = '▲';
        } else {
            resultDiv.style.display = 'none';
            resultDiv.classList.remove('show');
            arrow.textContent = '▼';
        }
    }
}

function toggleMultiSelect(type) {
    const dropdown = document.getElementById(`filter-${type}-dropdown`);
    const isOpen = dropdown.style.display === 'block';
    
    closeAllDropdowns();
    
    if (!isOpen) {
        dropdown.style.display = 'block';
        // Focus search input (if it exists - status filter doesn't have one)
        const searchInput = document.getElementById(`${type}-search`);
        if (searchInput) {
            setTimeout(() => {
                searchInput.focus();
            }, 10);
        }
    }
}

function closeAllDropdowns() {
    document.querySelectorAll('.multi-select-dropdown').forEach(function(dropdown) {
        dropdown.style.display = 'none';
    });
}

function filterOptions(type, searchTerm) {
    const options = document.querySelectorAll(`#${type}-options .multi-select-option`);
    const term = searchTerm.toLowerCase();
    
    options.forEach(function(option) {
        const label = option.querySelector('label').textContent.toLowerCase();
        if (label.includes(term)) {
            option.style.display = 'flex';
        } else {
            option.style.display = 'none';
        }
    });
}

function reorderDropdownOptions(type) {
    // Reorder options to show selected items at the top
    const optionsContainer = document.getElementById(`${type}-options`);
    if (!optionsContainer) return;
    
    const allOptions = Array.from(optionsContainer.querySelectorAll('.multi-select-option'));
    const selectedOptions = [];
    const unselectedOptions = [];
    
    allOptions.forEach(function(option) {
        const checkbox = option.querySelector('input[type="checkbox"]');
        if (checkbox && checkbox.checked) {
            selectedOptions.push(option);
            option.classList.add('selected');
        } else {
            unselectedOptions.push(option);
            option.classList.remove('selected');
        }
    });
    
    // Clear container
    optionsContainer.innerHTML = '';
    
    // Append selected options first
    selectedOptions.forEach(function(option) {
        optionsContainer.appendChild(option);
    });
    
    // Append unselected options after
    unselectedOptions.forEach(function(option) {
        optionsContainer.appendChild(option);
    });
}

function toggleFilter(type, value, event) {
    // Prevent double-firing if called from both onclick and onchange
    if (event) {
        event.stopPropagation();
    }
    
    // Decode HTML entities
    const decodedValue = value.replace(/&quot;/g, '"').replace(/&#39;/g, "'");
    const index = selectedFilters[type].indexOf(decodedValue);
    const wasSelected = index > -1;
    
    // Get checkbox to check its current state (in case it was toggled by user click)
    let checkbox = null;
    if (type === 'status') {
        checkbox = document.getElementById(`filter-status-${decodedValue}`);
    } else {
        // For dynamically populated filters (city, title, company, country), find by value
        const optionsContainer = document.getElementById(`${type}-options`);
        if (optionsContainer) {
            const checkboxes = optionsContainer.querySelectorAll('input[type="checkbox"]');
            for (let i = 0; i < checkboxes.length; i++) {
                // Decode the value to compare
                const checkboxValue = checkboxes[i].value.replace(/&quot;/g, '"').replace(/&#39;/g, "'");
                if (checkboxValue === decodedValue) {
                    checkbox = checkboxes[i];
                    break;
                }
            }
        }
    }
    
    // If checkbox exists, use its checked state as source of truth
    if (checkbox) {
        const isChecked = checkbox.checked;
        if (isChecked && !wasSelected) {
            // Checkbox is checked but not in our array - add it
            selectedFilters[type].push(decodedValue);
        } else if (!isChecked && wasSelected) {
            // Checkbox is unchecked but in our array - remove it
            selectedFilters[type].splice(index, 1);
        }
        // If states match, no change needed
    } else {
        // No checkbox, use toggle logic
        if (wasSelected) {
            selectedFilters[type].splice(index, 1);
        } else {
            selectedFilters[type].push(decodedValue);
        }
    }
    
    // If hidden filter is being selected, reload page with hidden jobs
    // But preserve all other filter states
    if (type === 'status' && decodedValue === 'hidden') {
        const isNowSelected = selectedFilters.status.includes('hidden');
        const url = new URL(window.location.href);
        
        if (isNowSelected) {
            // Store all current filter states in URL before reloading
            url.searchParams.set('include_hidden', 'true');
            // Store status filters
            if (selectedFilters.status.length > 0) {
                url.searchParams.set('status_filters', selectedFilters.status.join(','));
            }
            // Store other filters if they exist
            if (selectedFilters.city.length > 0) {
                url.searchParams.set('city_filters', selectedFilters.city.join(','));
            }
            if (selectedFilters.title.length > 0) {
                url.searchParams.set('title_filters', selectedFilters.title.join(','));
            }
            if (selectedFilters.company.length > 0) {
                url.searchParams.set('company_filters', selectedFilters.company.join(','));
            }
            if (selectedFilters.country.length > 0) {
                url.searchParams.set('country_filters', selectedFilters.country.join(','));
            }
            window.location.href = url.toString();
            return; // Don't continue, page will reload
        } else {
            // Deselecting hidden - check if we should reload
            if (url.searchParams.get('include_hidden') === 'true') {
                url.searchParams.delete('include_hidden');
                // Preserve other filters
                if (selectedFilters.status.length > 0) {
                    url.searchParams.set('status_filters', selectedFilters.status.join(','));
                } else {
                    url.searchParams.delete('status_filters');
                }
                window.location.href = url.toString();
                return; // Don't continue, page will reload
            }
        }
    }
    
    // Update filter display and apply filters immediately
    updateFilterDisplay(type);
    
    // Reorder dropdown options to show selected items at top (for non-status filters)
    if (type !== 'status') {
        reorderDropdownOptions(type);
    }
    
    // Apply filters immediately without delay
    applyAllFilters();
    saveFiltersToStorage(); // Auto-save filters when they change
}

function updateFilterDisplay(type) {
    const count = selectedFilters[type].length;
    const countElement = document.getElementById(`${type}-count`);
    
    if (!countElement) return;
    
    if (count === 0) {
        if (type === 'city') {
            countElement.textContent = 'All Cities';
        } else if (type === 'title') {
            countElement.textContent = 'All Job Titles';
        } else if (type === 'company') {
            countElement.textContent = 'All Companies';
        } else if (type === 'country') {
            countElement.textContent = 'All Countries';
        } else if (type === 'status') {
            countElement.textContent = 'All Status';
        }
    } else {
        countElement.textContent = `${count} selected`;
    }
}

function parseJobDate(dateString) {
    /**
     * Parse job date string to Date object.
     * Handles various date formats from different sources.
     */
    if (!dateString) return null;
    
    try {
        // Try ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
        const date = new Date(dateString);
        if (!isNaN(date.getTime())) {
            return date;
        }
        
        // Try parsing as just date part
        const dateOnly = dateString.split('T')[0];
        const date2 = new Date(dateOnly);
        if (!isNaN(date2.getTime())) {
            return date2;
        }
    } catch (e) {
        console.warn('Could not parse date:', dateString);
    }
    
    return null;
}

function isDateInRange(jobDate, range) {
    /**
     * Check if job date is within the specified range.
     * range: '24h', '3d', '1w', '2w', '1m', or empty string for all
     */
    if (!range || !jobDate) return true;
    
    const now = new Date();
    const jobDateObj = parseJobDate(jobDate);
    if (!jobDateObj) return true; // If we can't parse the date, show it
    
    const diffMs = now - jobDateObj;
    const diffDays = diffMs / (1000 * 60 * 60 * 24);
    
    switch (range) {
        case '24h':
            return diffDays <= 1;
        case '3d':
            return diffDays <= 3;
        case '1w':
            return diffDays <= 7;
        case '2w':
            return diffDays <= 14;
        case '1m':
            return diffDays <= 30;
        default:
            return true;
    }
}

function applyAllFilters() {
    const searchTerm = document.getElementById('search-bar') ? document.getElementById('search-bar').value.toLowerCase() : '';
    const sortBy = document.getElementById('sort-by') ? document.getElementById('sort-by').value : '';
    const dateFilter = document.getElementById('filter-date') ? document.getElementById('filter-date').value : '';
    
    const jobItems = document.querySelectorAll('.job-item');
    const visibleJobs = [];
    
    jobItems.forEach(function(jobItem) {
        let shouldShow = true;
        
        // Apply search filter
        if (searchTerm) {
            const jobContent = jobItem.textContent.toLowerCase();
            if (!jobContent.includes(searchTerm)) {
                shouldShow = false;
            }
        }
        
        // Apply date filter
        if (shouldShow && dateFilter) {
            const jobDate = jobItem.getAttribute('data-date');
            if (!isDateInRange(jobDate, dateFilter)) {
                shouldShow = false;
            }
        }
        
        // Apply city filter (multiple selection) - case insensitive
        if (shouldShow && selectedFilters.city.length > 0) {
            const jobCity = (jobItem.getAttribute('data-city') || '').toLowerCase();
            const selectedCitiesLower = selectedFilters.city.map(c => c.toLowerCase());
            if (!selectedCitiesLower.includes(jobCity)) {
                shouldShow = false;
            }
        }
        
        // Apply title filter (multiple selection) - case insensitive
        if (shouldShow && selectedFilters.title.length > 0) {
            const jobTitle = (jobItem.getAttribute('data-title') || '').toLowerCase();
            const selectedTitlesLower = selectedFilters.title.map(t => t.toLowerCase());
            if (!selectedTitlesLower.includes(jobTitle)) {
                shouldShow = false;
            }
        }
        
        // Apply company filter (multiple selection) - case insensitive
        if (shouldShow && selectedFilters.company.length > 0) {
            const jobCompany = (jobItem.getAttribute('data-company') || '').toLowerCase();
            const selectedCompaniesLower = selectedFilters.company.map(c => c.toLowerCase());
            if (!selectedCompaniesLower.includes(jobCompany)) {
                shouldShow = false;
            }
        }
        
        // Apply country filter (multiple selection) - case insensitive
        if (shouldShow && selectedFilters.country.length > 0) {
            const jobLocation = jobItem.getAttribute('data-city') || '';
            const jobCountry = extractCountry(jobLocation).toLowerCase();
            const selectedCountriesLower = selectedFilters.country.map(c => c.toLowerCase());
            if (!selectedCountriesLower.includes(jobCountry)) {
                shouldShow = false;
            }
        }
        
        // Apply status filter (saved, applied, interview, rejected, hidden)
        // ALL selected statuses must match (AND logic) - job must have EVERY selected status
        if (shouldShow && selectedFilters.status.length > 0) {
            // Get job status attributes - handle string, number, and float values
            const dataSaved = jobItem.getAttribute('data-saved');
            const jobSaved = dataSaved === '1' || dataSaved === 1 || dataSaved === '1.0' || parseFloat(dataSaved) === 1;
            
            const dataApplied = jobItem.getAttribute('data-applied');
            const jobApplied = dataApplied === '1' || dataApplied === 1 || dataApplied === '1.0' || parseFloat(dataApplied) === 1;
            
            const jobInterview = jobItem.classList.contains('job-item-interview');
            const jobRejected = jobItem.classList.contains('job-item-rejected');
            
            // Check data-hidden attribute (can be '1', 1, 1.0, 'true', or check class)
            const dataHidden = jobItem.getAttribute('data-hidden');
            const jobHidden = dataHidden === '1' || dataHidden === 1 || dataHidden === '1.0' || parseFloat(dataHidden) === 1 || dataHidden === 'true' || jobItem.classList.contains('job-item-hidden');
            
            // Check if job matches ALL selected statuses (AND logic)
            // A job must have EVERY selected status to be shown
            let matchesAllStatuses = true;
            for (let i = 0; i < selectedFilters.status.length; i++) {
                const status = selectedFilters.status[i];
                let statusMatches = false;
                
                // Check each status type
                if (status === 'saved') {
                    statusMatches = jobSaved;
                } else if (status === 'applied') {
                    statusMatches = jobApplied;
                } else if (status === 'interview') {
                    statusMatches = jobInterview;
                } else if (status === 'rejected') {
                    statusMatches = jobRejected;
                } else if (status === 'hidden') {
                    statusMatches = jobHidden;
                }
                
                // If this selected status doesn't match, the job doesn't match all statuses
                if (!statusMatches) {
                    matchesAllStatuses = false;
                    break; // No need to check remaining statuses
                }
            }
            
            // Hide job if it doesn't match all selected statuses
            if (!matchesAllStatuses) {
                shouldShow = false;
            }
        }
        
        // Show or hide the job item
        if (shouldShow) {
            jobItem.classList.remove('hidden');
            visibleJobs.push(jobItem);
        } else {
            jobItem.classList.add('hidden');
        }
    });
    
    // Sort the visible jobs (selected jobs will be at the top)
    if (visibleJobs.length > 0) {
        sortJobs(visibleJobs, sortBy);
    }
    
    // Update visible jobs list for keyboard navigation
    updateVisibleJobsList();
}

function updateVisibleJobsList() {
    // Get all visible (not hidden) job items
    const allJobItems = document.querySelectorAll('.job-item');
    visibleJobItems = Array.from(allJobItems).filter(function(jobItem) {
        return !jobItem.classList.contains('hidden');
    });
    
    // Reset focused index if current focus is out of bounds
    if (focusedJobIndex >= visibleJobItems.length) {
        focusedJobIndex = -1;
    }
}

function sortJobs(jobItems, sortOption) {
    const jobsContainer = document.getElementById('jobs-container');
    
    // Collect all hidden jobs before removing anything
    const allJobItems = Array.from(jobsContainer.querySelectorAll('.job-item'));
    const hiddenJobs = allJobItems.filter(function(jobItem) {
        return jobItem.classList.contains('hidden');
    });
    
    // Sort the visible jobs array
    jobItems.sort(function(a, b) {
        let aValue, bValue;
        
        if (sortOption.startsWith('date')) {
            // Parse dates - assuming format like "YYYY-MM-DD" or similar
            aValue = a.getAttribute('data-date') || '';
            bValue = b.getAttribute('data-date') || '';
            
            // Try to parse as date, fallback to string comparison
            const aDate = new Date(aValue);
            const bDate = new Date(bValue);
            
            if (!isNaN(aDate.getTime()) && !isNaN(bDate.getTime())) {
                aValue = aDate.getTime();
                bValue = bDate.getTime();
            }
        } else if (sortOption.startsWith('title')) {
            aValue = (a.getAttribute('data-title') || '').toLowerCase();
            bValue = (b.getAttribute('data-title') || '').toLowerCase();
        } else if (sortOption.startsWith('company')) {
            aValue = (a.getAttribute('data-company') || '').toLowerCase();
            bValue = (b.getAttribute('data-company') || '').toLowerCase();
        } else if (sortOption.startsWith('city')) {
            aValue = (a.getAttribute('data-city') || '').toLowerCase();
            bValue = (b.getAttribute('data-city') || '').toLowerCase();
        }
        
        // Determine sort direction
        const isDescending = sortOption.endsWith('-desc');
        
        if (aValue < bValue) {
            return isDescending ? 1 : -1;
        } else if (aValue > bValue) {
            return isDescending ? -1 : 1;
        } else {
            return 0;
        }
    });
    
    // Remove all job items from container
    allJobItems.forEach(function(jobItem) {
        jobItem.remove();
    });
    
    // Create fragment for visible jobs
    const visibleFragment = document.createDocumentFragment();
    jobItems.forEach(function(jobItem) {
        visibleFragment.appendChild(jobItem);
    });
    
    // Append sorted visible jobs first
    jobsContainer.appendChild(visibleFragment);
    
    // Append hidden jobs at the end
    hiddenJobs.forEach(function(jobItem) {
        jobsContainer.appendChild(jobItem);
    });
}

async function showJobDetails(jobId) {
    // Hide preview when clicking to view details
    hideJobPreview();
    
    if (selectedJob !== null) {
        selectedJob.classList.remove('job-item-selected');
    }
    console.log('Showing job details: ' + jobId); 
    var newSelectedJob = document.querySelector(`.job-item[data-job-id="${jobId}"]`);
    newSelectedJob.classList.add('job-item-selected');
    selectedJob = newSelectedJob;
    
    // Update focused index to match selected job
    updateVisibleJobsList();
    const jobIndex = visibleJobItems.indexOf(newSelectedJob);
    if (jobIndex >= 0) {
        focusedJobIndex = jobIndex;
        // Remove focus class from all jobs, add to selected
        visibleJobItems.forEach(function(item) {
            item.classList.remove('job-item-focused');
        });
        newSelectedJob.classList.add('job-item-focused');
    }

    const response = await fetch('/job_details/' + jobId);
    const jobData = await response.json();

    updateJobDetails(jobData);

    if ('cover_letter' in jobData) {
        updateCoverLetter(jobData.cover_letter);
    } else {
        updateCoverLetter(null);
    }
}





function updateCoverLetter(coverLetter) {
    var coverLetterDisplay = document.getElementById('cover-letter-display');
    var coverLetterContent = document.getElementById('cover-letter-content');
    var coverLetterActions = document.getElementById('cover-letter-actions');
    var coverLetterPlaceholder = document.getElementById('cover-letter-placeholder');
    var generateBtn = document.getElementById('generate-cover-letter-btn');
    
    if (coverLetter === null || !coverLetter) {
        if (coverLetterDisplay) coverLetterDisplay.style.display = 'none';
        if (coverLetterActions) coverLetterActions.style.display = 'none';
        if (coverLetterPlaceholder) coverLetterPlaceholder.style.display = 'block';
        if (generateBtn) generateBtn.style.display = 'inline-block';
    } else {
        if (coverLetterDisplay) coverLetterDisplay.style.display = 'block';
        if (coverLetterContent) coverLetterContent.textContent = coverLetter;
        if (coverLetterActions) coverLetterActions.style.display = 'flex';
        if (coverLetterPlaceholder) coverLetterPlaceholder.style.display = 'none';
        if (generateBtn) generateBtn.style.display = 'none';
    }
}

function openCoverLetterFullscreen() {
    var modal = document.getElementById('cover-letter-modal');
    var modalContent = document.getElementById('cover-letter-modal-content');
    var coverLetterContent = document.getElementById('cover-letter-content');
    
    if (modal && modalContent && coverLetterContent) {
        modalContent.textContent = coverLetterContent.textContent;
        modal.style.display = 'block';
        document.body.style.overflow = 'hidden'; // Prevent background scrolling
    }
}

function closeCoverLetterFullscreen() {
    var modal = document.getElementById('cover-letter-modal');
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = 'auto'; // Restore scrolling
    }
}

function downloadCoverLetterPDF() {
    if (!currentCoverLetterJobId) {
        alert('No cover letter available to download');
        return;
    }
    
    // Open PDF in new tab (which will trigger download)
    window.open('/api/cover-letter/pdf/' + currentCoverLetterJobId, '_blank');
}

function downloadCoverLetterDOCX() {
    if (!currentCoverLetterJobId) {
        alert('No cover letter available to download');
        return;
    }
    
    // Open DOCX in new tab (which will trigger download)
    window.open('/api/cover-letter/docx/' + currentCoverLetterJobId, '_blank');
}

function openLatexModal() {
    if (!currentCoverLetterJobId) {
        alert('No cover letter available');
        return;
    }
    
    var modal = document.getElementById('latex-modal');
    var textarea = document.getElementById('latex-textarea');
    var copySuccess = document.getElementById('copy-success');
    
    if (!modal || !textarea) return;
    
    // Hide success message
    if (copySuccess) copySuccess.style.display = 'none';
    
    // Fetch LaTeX formatted text
    fetch('/api/cover-letter/latex/' + currentCoverLetterJobId)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert('Error: ' + data.error);
                return;
            }
            
            // Set the LaTeX code in the textarea
            textarea.value = data.latex;
            
            // Show modal
            modal.style.display = 'block';
            document.body.style.overflow = 'hidden';
            
            // Select all text for easy copying
            textarea.select();
        })
        .catch(error => {
            console.error('Error loading LaTeX:', error);
            alert('Error loading LaTeX code');
        });
}

function closeLatexModal() {
    var modal = document.getElementById('latex-modal');
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = 'auto';
    }
}

function copyLatexToClipboard() {
    var textarea = document.getElementById('latex-textarea');
    var copySuccess = document.getElementById('copy-success');
    
    if (!textarea) return;
    
    // Select and copy
    textarea.select();
    textarea.setSelectionRange(0, 99999); // For mobile devices
    
    try {
        document.execCommand('copy');
        
        // Show success message
        if (copySuccess) {
            copySuccess.style.display = 'block';
            setTimeout(function() {
                copySuccess.style.display = 'none';
            }, 2000);
        }
        
        // Visual feedback
        textarea.style.backgroundColor = '#d4edda';
        setTimeout(function() {
            textarea.style.backgroundColor = '#f9f9f9';
        }, 300);
    } catch (err) {
        console.error('Failed to copy:', err);
        alert('Failed to copy. Please select and copy manually.');
    }
}

// Close modal when clicking outside of it
window.onclick = function(event) {
    var modal = document.getElementById('cover-letter-modal');
    var latexModal = document.getElementById('latex-modal');
    var analysisModal = document.getElementById('analysis-modal');
    var analysisHistoryModal = document.getElementById('analysis-history-modal');
    if (event.target == modal) {
        closeCoverLetterFullscreen();
    }
    if (event.target == latexModal) {
        closeLatexModal();
    }
    if (event.target == analysisModal) {
        closeAnalysisModal();
    }
    if (event.target == analysisHistoryModal) {
        closeAnalysisHistoryModal();
    }
}



function updateJobDetails(job) {
    var jobDetailsDiv = document.getElementById('job-details');
    var coverLetterDiv = document.getElementById('bottom-pane'); // Get the cover letter div
    console.log('Updating job details: ' + job.id); // Log the jobId here
    
    jobDetailsDiv.innerHTML = AnalysisTemplates.formatJobDetails(job);
    
    // Update current job ID for cover letter generation
    currentCoverLetterJobId = job.id;
    
    // Check provider and show/hide model selector
    checkProviderAndLoadModels();
    
    // Update cover letter display
    if (job.cover_letter) {
        updateCoverLetter(job.cover_letter);
        var generateBtn = document.getElementById('generate-cover-letter-btn');
        if (generateBtn) generateBtn.style.display = 'none';
    } else {
        updateCoverLetter(null);
        var generateBtn = document.getElementById('generate-cover-letter-btn');
        if (generateBtn) {
            generateBtn.style.display = 'inline-block';
            generateBtn.onclick = function() { generateCoverLetter(); };
        }
    }
}

async function checkProviderAndLoadModels() {
    try {
        // Fetch config to check provider
        const response = await fetch('/api/config');
        const config = await response.json();
        const provider = (config.cover_letter_provider || 'template').toLowerCase();
        
        var modelSelect = document.getElementById('ollama-model-select');
        if (modelSelect) {
            if (provider === 'ollama') {
                modelSelect.style.display = 'block';
                await loadOllamaModels();
            } else {
                modelSelect.style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Error checking provider:', error);
    }
}

async function loadOllamaModels() {
    var modelSelect = document.getElementById('ollama-model-select');
    if (!modelSelect) return;
    
    modelSelect.innerHTML = '<option value="">Loading models...</option>';
    
    try {
        // Fetch models and config in parallel
        const [modelsResponse, configResponse] = await Promise.all([
            fetch('/api/ollama/models'),
            fetch('/api/config')
        ]);
        
        const modelsData = await modelsResponse.json();
        const config = await configResponse.json();
        
        if (modelsData.models && modelsData.models.length > 0) {
            modelSelect.innerHTML = '';
            modelsData.models.forEach(function(model) {
                var option = document.createElement('option');
                option.value = model;
                option.textContent = model;
                modelSelect.appendChild(option);
            });
            
            // Auto-select last used model from config
            var defaultModel = config.ollama_model;
            if (defaultModel) {
                // Try to find and select the saved model
                var found = false;
                for (var i = 0; i < modelSelect.options.length; i++) {
                    if (modelSelect.options[i].value === defaultModel) {
                        modelSelect.value = defaultModel;
                        found = true;
                        break;
                    }
                }
                // If saved model not in list, add it silently
                if (!found && defaultModel) {
                    var option = document.createElement('option');
                    option.value = defaultModel;
                    option.textContent = defaultModel;
                    modelSelect.appendChild(option);
                    modelSelect.value = defaultModel;
                }
            }
            
            // Save model to config when user changes selection
            modelSelect.addEventListener('change', function() {
                if (this.value) {
                    saveOllamaModelToConfig(this.value);
                }
            });
        } else {
            modelSelect.innerHTML = '<option value="">No models available</option>';
        }
    } catch (error) {
        console.error('Error loading Ollama models:', error);
        modelSelect.innerHTML = '<option value="">Error loading models</option>';
    }
}

async function saveOllamaModelToConfig(model) {
    try {
        // Get current config
        const configResponse = await fetch('/api/config');
        const config = await configResponse.json();
        
        // Update model
        config.ollama_model = model;
        
        // Save to config
        const saveResponse = await fetch('/api/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        });
        
        const result = await saveResponse.json();
        if (result.error) {
            console.error('Error saving model to config:', result.error);
        } else {
            console.log('Model saved to config:', model);
        }
    } catch (error) {
        console.error('Error saving model to config:', error);
    }
}


function toggleApplied(jobId) {
    var jobCard = document.querySelector(`.job-item[data-job-id="${jobId}"]`);
    var isApplied = jobCard && jobCard.getAttribute('data-applied') === '1';
    var endpoint = isApplied ? '/unmark_applied/' : '/mark_applied/';
    
    fetch(endpoint + jobId, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            console.log(data);
            if (data.success) {
                if (isApplied) {
                    // Unmark applied
                    if (jobCard) {
                        jobCard.classList.remove('job-item-applied');
                        jobCard.setAttribute('data-applied', '0');
                        
                        // Remove Applied badge
                        var jobContent = jobCard.querySelector('.job-content');
                        if (jobContent) {
                            var title = jobContent.querySelector('h3');
                            if (title) {
                                var badge = title.querySelector('.applied-badge');
                                if (badge) {
                                    badge.remove();
                                }
                            }
                        }
                    }
                } else {
                    // Mark as applied
                    if (jobCard) {
                        jobCard.classList.add('job-item-applied');
                        jobCard.setAttribute('data-applied', '1');
                        
                        // Add Applied badge if it doesn't exist
                        var jobContent = jobCard.querySelector('.job-content');
                        var title = jobContent.querySelector('h3');
                        if (title && !title.querySelector('.applied-badge')) {
                            var badge = document.createElement('span');
                            badge.className = 'applied-badge';
                            badge.textContent = 'Applied';
                            title.appendChild(badge);
                        }
                    }
                }
                
                // Update button text
                var btn = document.getElementById('applied-btn-' + jobId);
                if (btn) {
                    btn.textContent = isApplied ? 'Mark Applied' : 'Unmark Applied';
                }
                
                // Refresh job details to update button states
                showJobDetails(jobId);
            }
        })
        .catch(error => {
            console.error('Error toggling applied status:', error);
        });
}

function markAsApplied(jobId) {
    // Legacy function - redirect to toggle
    toggleApplied(jobId);
}

function removeAppliedBadge(jobId) {
    var jobCard = document.querySelector(`.job-item[data-job-id="${jobId}"]`);
    if (jobCard) {
        jobCard.classList.remove('job-item-applied');
        jobCard.setAttribute('data-applied', '0');
        
        // Remove Applied badge
        var jobContent = jobCard.querySelector('.job-content');
        if (jobContent) {
            var title = jobContent.querySelector('h3');
            if (title) {
                var badge = title.querySelector('.applied-badge');
                if (badge) {
                    badge.remove();
                }
            }
        }
    }
}

// Listen for messages from application tracker
window.addEventListener('message', function(event) {
    if (event.data && event.data.type === 'removeAppliedBadge') {
        removeAppliedBadge(event.data.jobId);
    }
});

// Check localStorage for badge removal signals
function checkForBadgeRemovals() {
    const keys = Object.keys(localStorage);
    keys.forEach(function(key) {
        if (key.startsWith('removeAppliedBadge_')) {
            const jobId = key.replace('removeAppliedBadge_', '');
            removeAppliedBadge(parseInt(jobId));
            localStorage.removeItem(key);
        }
    });
}

// Check on page load and visibility change
document.addEventListener('DOMContentLoaded', function() {
    checkForBadgeRemovals();
});

document.addEventListener('visibilitychange', function() {
    if (!document.hidden) {
        checkForBadgeRemovals();
    }
});

var currentCoverLetterJobId = null;
var coverLetterStatusInterval = null;

function generateCoverLetter() {
    if (currentCoverLetterJobId) {
        startCoverLetterGeneration(currentCoverLetterJobId);
    }
}

function startCoverLetterGeneration(jobId) {
    currentCoverLetterJobId = jobId;
    
    // Show loading state
    var statusDiv = document.getElementById('cover-letter-status');
    var displayDiv = document.getElementById('cover-letter-display');
    var placeholderDiv = document.getElementById('cover-letter-placeholder');
    var generateBtn = document.getElementById('generate-cover-letter-btn');
    
    if (statusDiv) {
        statusDiv.style.display = 'block';
        statusDiv.className = 'cover-letter-status';
        statusDiv.innerHTML = '<span class="loading-spinner"></span>Starting cover letter generation...';
    }
    if (displayDiv) displayDiv.style.display = 'none';
    if (placeholderDiv) placeholderDiv.style.display = 'none';
    if (generateBtn) generateBtn.disabled = true;
    if (generateBtn) generateBtn.innerHTML = 'Generating...';
    
    // Start polling for status
    if (coverLetterStatusInterval) {
        clearInterval(coverLetterStatusInterval);
    }
    coverLetterStatusInterval = setInterval(checkCoverLetterStatus, 500);
    
    // Get selected model if Ollama provider
    var modelSelect = document.getElementById('ollama-model-select');
    var selectedModel = null;
    if (modelSelect && modelSelect.style.display !== 'none') {
        selectedModel = modelSelect.value;
    }
    
    // Start the generation
    var requestBody = {};
    if (selectedModel) {
        requestBody.model = selectedModel;
    }
    
    fetch('/get_CoverLetter/' + jobId, { 
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: Object.keys(requestBody).length > 0 ? JSON.stringify(requestBody) : undefined
    })
        .then(response => response.json())
        .then(data => {
            console.log(data);
            if (data.cover_letter) {
                // Stop polling
                if (coverLetterStatusInterval) {
                    clearInterval(coverLetterStatusInterval);
                    coverLetterStatusInterval = null;
                }
                
                // Hide status, show cover letter
                if (statusDiv) statusDiv.style.display = 'none';
                updateCoverLetter(data.cover_letter);
                
                // Refresh job details to show updated cover letter
                showJobDetails(jobId);
            } else if (data.error) {
                // Show error
                if (statusDiv) {
                    statusDiv.className = 'cover-letter-error';
                    statusDiv.innerHTML = '[ERROR] ' + data.error;
                }
                if (generateBtn) generateBtn.disabled = false;
                if (generateBtn) generateBtn.innerHTML = 'Generate Cover Letter';
            }
        })
        .catch(error => {
            console.error('Error generating cover letter:', error);
            if (statusDiv) {
                statusDiv.className = 'cover-letter-error';
                statusDiv.innerHTML = '[ERROR] Failed to generate cover letter: ' + error.message;
            }
            if (generateBtn) generateBtn.disabled = false;
            if (generateBtn) generateBtn.innerHTML = 'Generate Cover Letter';
            if (coverLetterStatusInterval) {
                clearInterval(coverLetterStatusInterval);
                coverLetterStatusInterval = null;
            }
        });
}

function checkCoverLetterStatus() {
    fetch('/api/cover-letter/status')
        .then(response => response.json())
        .then(data => {
            var statusDiv = document.getElementById('cover-letter-status');
            if (statusDiv && data.running) {
                statusDiv.style.display = 'block';
                statusDiv.className = 'cover-letter-status';
                statusDiv.innerHTML = '<span class="loading-spinner"></span>' + (data.message || 'Generating cover letter...');
            } else if (statusDiv && data.completed) {
                // Status will be handled by the main fetch response
                if (coverLetterStatusInterval) {
                    clearInterval(coverLetterStatusInterval);
                    coverLetterStatusInterval = null;
                }
            }
        })
        .catch(error => {
            console.error('Error checking cover letter status:', error);
        });
}

function markAsCoverLetter(jobId) {
    console.log('Generating cover letter for job: ' + jobId);
    currentCoverLetterJobId = jobId;
    startCoverLetterGeneration(jobId);
}

function toggleRejected(jobId) {
    var jobCard = document.querySelector(`.job-item[data-job-id="${jobId}"]`);
    var isRejected = jobCard && jobCard.classList.contains('job-item-rejected');
    var endpoint = isRejected ? '/unmark_rejected/' : '/mark_rejected/';
    
    fetch(endpoint + jobId, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            console.log(data);
            if (data.success) {
                if (isRejected) {
                    // Unmark rejected
                    if (jobCard) {
                        jobCard.classList.remove('job-item-rejected');
                    }
                } else {
                    // Mark as rejected
                    if (jobCard) {
                        jobCard.classList.add('job-item-rejected');
                    }
                }
                
                // Update button text
                var btn = document.getElementById('rejected-btn-' + jobId);
                if (btn) {
                    btn.textContent = isRejected ? 'Mark Rejected' : 'Unmark Rejected';
                }
                
                // Refresh job details to update button states
                showJobDetails(jobId);
            }
        })
        .catch(error => {
            console.error('Error toggling rejected status:', error);
        });
}

function markAsRejected(jobId) {
    // Legacy function - redirect to toggle
    toggleRejected(jobId);
}

function hideJob(jobId) {
    fetch('/hide_job/' + jobId, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                var jobCard = document.querySelector(`.job-item[data-job-id="${jobId}"]`);
                if (jobCard) {
                    // Mark as hidden
                    jobCard.setAttribute('data-hidden', '1');
                    jobCard.classList.add('job-item-hidden');
                    
                    // Add hidden badge
                    var jobContent = jobCard.querySelector('.job-content');
                    if (jobContent) {
                        var title = jobContent.querySelector('h3');
                        if (title && !title.querySelector('.hidden-badge')) {
                            var badge = document.createElement('span');
                            badge.className = 'hidden-badge';
                            badge.textContent = 'Hidden';
                            title.appendChild(badge);
                        }
                    }
                    
                    // Hide the job card visually (but keep in DOM for filtering)
                    jobCard.classList.add('hidden');
                }
                
                // Find the next sibling in the DOM that is a job-item
                var nextJobCard = jobCard ? jobCard.nextElementSibling : null;
                while(nextJobCard && !nextJobCard.classList.contains('job-item')) {
                    nextJobCard = nextJobCard.nextElementSibling;
                }
                
                // If a next job exists, show its details
                if (nextJobCard) {
                    var nextJobId = nextJobCard.getAttribute('data-job-id');
                    showJobDetails(nextJobId);
                } else {
                    // If no next job exists, clear the job details div
                    var jobDetailsDiv = document.getElementById('job-details');
                    if (jobDetailsDiv) {
                        jobDetailsDiv.innerHTML = '';
                    }
                }
            }
        });
}

function unhideJob(jobId) {
    fetch('/unhide_job/' + jobId, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                var jobCard = document.querySelector(`.job-item[data-job-id="${jobId}"]`);
                if (jobCard) {
                    // Remove hidden status
                    jobCard.setAttribute('data-hidden', '0');
                    jobCard.classList.remove('job-item-hidden');
                    jobCard.classList.remove('hidden');
                    
                    // Remove hidden badge
                    var jobContent = jobCard.querySelector('.job-content');
                    if (jobContent) {
                        var title = jobContent.querySelector('h3');
                        if (title) {
                            var hiddenBadge = title.querySelector('.hidden-badge');
                            if (hiddenBadge) {
                                hiddenBadge.remove();
                            }
                        }
                    }
                }
                
                // Refresh job details to update the button
                showJobDetails(jobId);
            }
        });
}


function toggleInterview(jobId) {
    var jobCard = document.querySelector(`.job-item[data-job-id="${jobId}"]`);
    var isInterview = jobCard && jobCard.classList.contains('job-item-interview');
    var endpoint = isInterview ? '/unmark_interview/' : '/mark_interview/';
    
    fetch(endpoint + jobId, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            console.log(data);
            if (data.success) {
                if (isInterview) {
                    // Unmark interview
                    if (jobCard) {
                        jobCard.classList.remove('job-item-interview');
                    }
                } else {
                    // Mark as interview
                    if (jobCard) {
                        jobCard.classList.add('job-item-interview');
                    }
                }
                
                // Update button text
                var btn = document.getElementById('interview-btn-' + jobId);
                if (btn) {
                    btn.textContent = isInterview ? 'Mark Interview' : 'Unmark Interview';
                }
                
                // Refresh job details to update button states
                showJobDetails(jobId);
            }
        })
        .catch(error => {
            console.error('Error toggling interview status:', error);
        });
}

function markAsInterview(jobId) {
    // Legacy function - redirect to toggle
    toggleInterview(jobId);
}

function toggleSaved(jobId) {
    var jobCard = document.querySelector(`.job-item[data-job-id="${jobId}"]`);
    if (!jobCard) {
        console.error('Job card not found for job ID:', jobId);
        return;
    }
    
    var isSaved = jobCard.getAttribute('data-saved') === '1';
    var saveBtn = document.getElementById('save-btn-' + jobId);
    
    // Update UI immediately for better UX
    if (isSaved) {
        // Unsave - update UI immediately
        jobCard.setAttribute('data-saved', '0');
        jobCard.classList.remove('job-item-saved');
        if (saveBtn) saveBtn.textContent = 'Save';
        
        // Remove saved badge
        var jobContent = jobCard.querySelector('.job-content');
        if (jobContent) {
            var title = jobContent.querySelector('h3');
            if (title) {
                var savedBadge = title.querySelector('.saved-badge');
                if (savedBadge) {
                    savedBadge.remove();
                }
            }
        }
    } else {
        // Save - update UI immediately
        jobCard.setAttribute('data-saved', '1');
        jobCard.classList.add('job-item-saved');
        if (saveBtn) saveBtn.textContent = 'Unsave';
        
        // Add saved badge
        var jobContent = jobCard.querySelector('.job-content');
        if (jobContent) {
            var title = jobContent.querySelector('h3');
            if (title && !title.querySelector('.saved-badge')) {
                var badge = document.createElement('span');
                badge.className = 'saved-badge';
                badge.textContent = 'Saved';
                title.appendChild(badge);
            }
        }
    }
    
    // Make API call
    var endpoint = isSaved ? '/unmark_saved/' : '/mark_saved/';
    
    fetch(endpoint + jobId, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            console.log(data);
            if (data.success) {
                // Ensure the job stays visible after status change
                // Don't reapply filters which might hide it
                jobCard.classList.remove('hidden');
            } else {
                // Revert UI changes if API call failed
                if (isSaved) {
                    jobCard.setAttribute('data-saved', '1');
                    jobCard.classList.add('job-item-saved');
                    if (saveBtn) saveBtn.textContent = 'Unsave';
                    var jobContent = jobCard.querySelector('.job-content');
                    if (jobContent) {
                        var title = jobContent.querySelector('h3');
                        if (title && !title.querySelector('.saved-badge')) {
                            var badge = document.createElement('span');
                            badge.className = 'saved-badge';
                            badge.textContent = 'Saved';
                            title.appendChild(badge);
                        }
                    }
                } else {
                    jobCard.setAttribute('data-saved', '0');
                    jobCard.classList.remove('job-item-saved');
                    if (saveBtn) saveBtn.textContent = 'Save';
                    var jobContent = jobCard.querySelector('.job-content');
                    if (jobContent) {
                        var title = jobContent.querySelector('h3');
                        if (title) {
                            var savedBadge = title.querySelector('.saved-badge');
                            if (savedBadge) {
                                savedBadge.remove();
                            }
                        }
                    }
                }
            }
        })
        .catch(error => {
            console.error('Error toggling saved status:', error);
            // Revert UI changes on error
            if (isSaved) {
                jobCard.setAttribute('data-saved', '1');
                jobCard.classList.add('job-item-saved');
                if (saveBtn) saveBtn.textContent = 'Unsave';
            } else {
                jobCard.setAttribute('data-saved', '0');
                jobCard.classList.remove('job-item-saved');
                if (saveBtn) saveBtn.textContent = 'Save';
            }
        });
}

var resizer = document.getElementById('resizer');
var jobDetails = document.getElementById('job-details');
var bottomPane = document.getElementById('bottom-pane');
var originalHeight, originalMouseY;

resizer.addEventListener('mousedown', function(e) {
    e.preventDefault();
    originalHeight = jobDetails.getBoundingClientRect().height;
    originalMouseY = e.pageY;
    document.addEventListener('mousemove', drag);
    document.addEventListener('mouseup', stopDrag);
});

function drag(e) {
    var delta = e.pageY - originalMouseY;
    jobDetails.style.height = (originalHeight + delta) + "px";
    bottomPane.style.height = `calc(100% - ${originalHeight + delta}px - 10px)`;
}

function stopDrag() {
    document.removeEventListener('mousemove', drag);
    document.removeEventListener('mouseup', stopDrag);
}

// Ollama Pipeline Functions
let pipelineData = {
    jobJson: null,
    resumeJson: null
};
let currentAnalysisJobId = null;

async function getOllamaConfig() {
    try {
        const response = await fetch('/api/config');
        const config = await response.json();
        return {
            base_url: config.ollama_base_url || 'http://localhost:11434',
            model: config.ollama_model || 'llama3.2:latest'
        };
    } catch (error) {
        console.error('Error fetching config:', error);
        return {
            base_url: 'http://localhost:11434',
            model: 'llama3.2:latest'
        };
    }
}

function updatePipelineStatus(step, status, message) {
    const statusEl = document.getElementById(`step${step}-status`);
    if (statusEl) {
        statusEl.className = `pipeline-status ${status}`;
        statusEl.textContent = message;
        statusEl.style.display = 'block';
    }
}

function formatJobJSON(job) {
    return AnalysisTemplates.formatJobJSON(job);
}

function formatResumeJSON(resume) {
    return AnalysisTemplates.formatResumeJSON(resume);
}

function formatMatchAnalysis(analysis) {
    return AnalysisTemplates.formatMatchAnalysis(analysis);
}

function formatResumeImprovement(text) {
    return AnalysisTemplates.formatResumeImprovement(text);
}

function escapeHtml(text) {
    return AnalysisTemplates.escapeHtml(text);
}

function showPipelineResult(step, data) {
    const resultEl = document.getElementById(`step${step}-result`);
    const jsonEl = document.getElementById(`step${step}-json`);
    if (resultEl && jsonEl) {
        let formattedHtml = '';
        
        if (typeof data === 'string') {
            // For Step 4 (improved resume), format as markdown
            formattedHtml = formatResumeImprovement(data);
        } else if (step === 4 && data.improved_resume) {
            // Handle Step 4 when data is an object with improved_resume property
            formattedHtml = formatResumeImprovement(data.improved_resume);
        } else {
            // Format JSON based on step
            switch(step) {
                case 1:
                    formattedHtml = formatJobJSON(data);
                    break;
                case 2:
                    formattedHtml = formatResumeJSON(data);
                    break;
                case 3:
                    formattedHtml = formatMatchAnalysis(data);
                    break;
                case 4:
                    formattedHtml = AnalysisTemplates.formatImprovements(data);
                    break;
                default:
                    // Fallback to JSON for unknown steps
                    formattedHtml = '<pre style="background: #f8f9fa; padding: 15px; border-radius: 5px; overflow-x: auto;">' + escapeHtml(JSON.stringify(data, null, 2)) + '</pre>';
            }
        }
        
        jsonEl.innerHTML = formattedHtml;
        
        // Step 1 and 2 remain hidden by default (user must toggle to view)
        // Step 3 and 4 are shown automatically
        if (step === 1 || step === 2) {
            // Keep hidden, user can toggle to view
            resultEl.style.display = 'none';
        } else {
            // Show automatically for Step 3 and 4
            resultEl.style.display = 'block';
            resultEl.classList.add('show');
        }
    }
}

async function openAnalysisModal(jobId) {
    currentAnalysisJobId = jobId;
    const modal = document.getElementById('analysis-modal');
    const modalContent = document.getElementById('analysis-modal-content');
    
    // Reset pipeline data
    pipelineData = {
        jobJson: null,
        resumeJson: null
    };
    
    // Get config first to check for default resume and model
    let config = {};
    try {
        const configResponse = await fetch('/api/config');
        config = await configResponse.json();
    } catch (error) {
        console.error('Error loading config:', error);
    }
    
    // Load available resumes
    let resumeOptions = '<option value="">Loading resumes...</option>';
    try {
        const resumeResponse = await fetch('/api/list-resumes');
        const resumeData = await resumeResponse.json();
        const defaultResumePath = config.resume_path || '';
        
        if (resumeData.resumes && resumeData.resumes.length > 0) {
            resumeOptions = '<option value="">Select a resume...</option>';
            resumeData.resumes.forEach(function(resume) {
                const isSelected = resume.path === defaultResumePath;
                resumeOptions += `<option value="${AnalysisTemplates.escapeHtml(resume.path)}"${isSelected ? ' selected' : ''}>${AnalysisTemplates.escapeHtml(resume.name)}</option>`;
            });
        } else {
            resumeOptions = '<option value="">No PDF files found in root folder</option>';
        }
    } catch (error) {
        console.error('Error loading resumes:', error);
        resumeOptions = '<option value="">Error loading resumes</option>';
    }
    
    // Load Ollama models
    let modelOptions = '<option value="">Loading models...</option>';
    try {
        const modelResponse = await fetch('/api/ollama/models');
        const modelData = await modelResponse.json();
        if (modelData.models && modelData.models.length > 0) {
            // Get default model from config
            const defaultModel = config.ollama_model || modelData.models[0];
            
            modelOptions = '';
            modelData.models.forEach(function(model) {
                modelOptions += AnalysisTemplates.getModelOption(model, model === defaultModel);
            });
        } else {
            modelOptions = '<option value="">No models available</option>';
        }
    } catch (error) {
        console.error('Error loading models:', error);
        modelOptions = '<option value="">Error loading models</option>';
    }
    
    // Build pipeline UI using templates
    let html = AnalysisTemplates.getModalContent();
    
    // Inject resume and model options (replace the empty select tags)
    html = html.replace('<select id="resume-selector" style="width: 100%; padding: 10px; border: 2px solid #4CAF50; border-radius: 5px; font-size: 14px; background-color: white;">', 
                        '<select id="resume-selector" style="width: 100%; padding: 10px; border: 2px solid #4CAF50; border-radius: 5px; font-size: 14px; background-color: white;">' + resumeOptions);
    html = html.replace('<select id="analysis-model-selector" style="width: 100%; padding: 10px; border: 2px solid #4CAF50; border-radius: 5px; font-size: 14px; background-color: white;">', 
                        '<select id="analysis-model-selector" style="width: 100%; padding: 10px; border: 2px solid #4CAF50; border-radius: 5px; font-size: 14px; background-color: white;">' + modelOptions);
    
    // Set up button click handler - use event listener only (no onclick attribute to avoid double-firing)
    html = html.replace('id="run-full-analysis-btn"', `id="run-full-analysis-btn"`);
    
    modalContent.innerHTML = html;
    modal.style.display = 'block';
    
    // Set up event listener (only one handler to prevent double-firing)
    setTimeout(function() {
        const runButton = document.getElementById('run-full-analysis-btn');
        if (runButton) {
            // Remove any existing listeners by cloning the button
            const newButton = runButton.cloneNode(true);
            runButton.parentNode.replaceChild(newButton, runButton);
            
            // Add single event listener
            newButton.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                
                // Prevent double-clicks
                if (newButton.disabled) {
                    console.log('Button already clicked, ignoring duplicate click');
                    return;
                }
                
                console.log('Button clicked via event listener, jobId:', jobId);
                runFullAnalysis(jobId);
            });
        }
    }, 100);
}

function closeAnalysisModal() {
    const modal = document.getElementById('analysis-modal');
    modal.style.display = 'none';
    currentAnalysisJobId = null;
    pipelineData = {
        jobJson: null,
        resumeJson: null
    };
}

async function openAnalysisHistory(jobId) {
    const modal = document.getElementById('analysis-history-modal');
    const modalContent = document.getElementById('analysis-history-content');
    
    try {
        // Fetch analysis history from backend
        const response = await fetch(`/api/analysis-history/${jobId}`);
        const data = await response.json();
        
        if (response.ok && data.analyses && data.analyses.length > 0) {
            let html = AnalysisTemplates.formatHistoryContainer();
            data.analyses.forEach(function(analysis, index) {
                html += AnalysisTemplates.formatHistoryEntry(analysis, index, data.analyses.length);
                
                // Parse and format the analysis data
                try {
                    const analysisData = JSON.parse(analysis.analysis_data);
                    let formattedHtml = '';
                    
                    // Check if it's a full analysis with steps
                    if (analysisData.step1 || analysisData.step2 || analysisData.step3 || analysisData.step4) {
                        if (analysisData.step1) {
                            const step1Id = 'hist-step1-' + index;
                            formattedHtml += AnalysisTemplates.getHistoryStepTemplate(1, step1Id, 'Step 1: Job JSON', formatJobJSON(analysisData.step1));
                        }
                        if (analysisData.step2) {
                            const step2Id = 'hist-step2-' + index;
                            formattedHtml += AnalysisTemplates.getHistoryStepTemplate(2, step2Id, 'Step 2: Resume JSON', formatResumeJSON(analysisData.step2));
                        }
                        if (analysisData.step3) {
                            formattedHtml += AnalysisTemplates.getHistoryStepTemplate(3, 'hist-step3-' + index, 'Step 3: Keyword Analysis', formatMatchAnalysis(analysisData.step3));
                        }
                        if (analysisData.step4) {
                            formattedHtml += AnalysisTemplates.getHistoryStepTemplate(4, 'hist-step4-' + index, 'Step 4: Resume Improvements', AnalysisTemplates.formatImprovements(analysisData.step4));
                        }
                    } else if (analysisData.keywords || analysisData.overallFit || analysisData.improvements || analysisData.aspirationalImprovements) {
                        // Combined analysis format (from run_full_analysis) - includes keywords, overallFit, improvements
                        // Show Step 3: Keyword Analysis
                        if (analysisData.keywords) {
                            const keywordAnalysis = { keywords: analysisData.keywords };
                            formattedHtml += AnalysisTemplates.getHistoryStepTemplate(3, 'hist-step3-' + index, 'Step 3: Keyword Analysis', formatMatchAnalysis(keywordAnalysis));
                        }
                        // Show Step 4: Resume Improvements (includes overallFit, improvements, aspirationalImprovements)
                        if (analysisData.overallFit || analysisData.improvements || analysisData.aspirationalImprovements) {
                            const improvementsData = {
                                overallFit: analysisData.overallFit || {},
                                improvements: analysisData.improvements || [],
                                aspirationalImprovements: analysisData.aspirationalImprovements || []
                            };
                            formattedHtml += AnalysisTemplates.getHistoryStepTemplate(4, 'hist-step4-' + index, 'Step 4: Resume Improvements', AnalysisTemplates.formatImprovements(improvementsData));
                        }
                    } else {
                        // Single analysis object - try to determine type
                        if (analysisData.title || analysisData.company) {
                            formattedHtml = formatJobJSON(analysisData);
                        } else if (analysisData.personalInfo || analysisData.workExperience) {
                            formattedHtml = formatResumeJSON(analysisData);
                        } else if (analysisData.overallFit || analysisData.improvements) {
                            formattedHtml = formatMatchAnalysis(analysisData);
                        } else {
                            // Fallback to JSON
                            formattedHtml = AnalysisTemplates.formatJSONFallback(analysisData);
                        }
                        formattedHtml = AnalysisTemplates.formatSingleAnalysisWrapper(formattedHtml);
                    }
                    
                    html += formattedHtml;
                } catch (e) {
                    // If parsing fails, show raw JSON
                    html += AnalysisTemplates.formatHistoryRawJSON(analysis.analysis_data);
                }
                html += AnalysisTemplates.formatHistoryEntryFooter();
            });
            html += AnalysisTemplates.formatHistoryContainerFooter();
            modalContent.innerHTML = html;
        } else {
            modalContent.innerHTML = AnalysisTemplates.formatHistoryEmpty();
        }
    } catch (error) {
        console.error('Error fetching analysis history:', error);
        modalContent.innerHTML = AnalysisTemplates.formatHistoryError(error.message);
    }
    
    modal.style.display = 'block';
}

function closeAnalysisHistoryModal() {
    const modal = document.getElementById('analysis-history-modal');
    modal.style.display = 'none';
}

async function runStep1(jobId) {
    try {
        updatePipelineStatus(1, 'loading', 'Extracting job JSON...');
        
        // Get job description
        const jobResponse = await fetch('/job_details/' + jobId);
        const jobData = await jobResponse.json();
        const jobText = jobData.job_description || '';
        
        if (!jobText) {
            updatePipelineStatus(1, 'error', 'No job description found');
            return;
        }
        
        // Get Ollama config
        const config = await getOllamaConfig();
        
        // Call API
        const response = await fetch('/api/ollama/structured-job', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                job_text: jobText,
                base_url: config.base_url,
                model: config.model
            })
        });
        
        const result = await response.json();
        
        if (response.ok && result.job_json) {
            pipelineData.jobJson = result.job_json;
            updatePipelineStatus(1, 'success', 'Job JSON extracted successfully!');
            showPipelineResult(1, result.job_json);
            
            // Enable Step 3 button
            const step3Button = document.getElementById('step3-button');
            if (step3Button) step3Button.disabled = false;
        } else {
            updatePipelineStatus(1, 'error', result.error || 'Failed to extract job JSON');
        }
    } catch (error) {
        console.error('Error in Step 1:', error);
        updatePipelineStatus(1, 'error', 'Error: ' + error.message);
    }
}

async function runStep2() {
    try {
        updatePipelineStatus(2, 'loading', 'Extracting resume JSON...');
        
        // Get Ollama config
        const config = await getOllamaConfig();
        
        // Call API (will use default resume path from config)
        const response = await fetch('/api/ollama/structured-resume', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                base_url: config.base_url,
                model: config.model
            })
        });
        
        const result = await response.json();
        
        if (response.ok && result.resume_json) {
            pipelineData.resumeJson = result.resume_json;
            updatePipelineStatus(2, 'success', 'Resume JSON extracted successfully!');
            showPipelineResult(2, result.resume_json);
            
            // Enable Step 3 button if Step 1 is also done
            if (pipelineData.jobJson) {
                const step3Button = document.getElementById('step3-button');
                if (step3Button) step3Button.disabled = false;
            }
            
            // Enable Step 4 button
            const step4Button = document.getElementById('step4-button');
            if (step4Button) step4Button.disabled = false;
        } else {
            updatePipelineStatus(2, 'error', result.error || 'Failed to extract resume JSON');
        }
    } catch (error) {
        console.error('Error in Step 2:', error);
        updatePipelineStatus(2, 'error', 'Error: ' + error.message);
    }
}

async function runStep3() {
    try {
        if (!pipelineData.jobJson || !pipelineData.resumeJson) {
            updatePipelineStatus(3, 'error', 'Please run Step 1 and Step 2 first');
            return;
        }
        
        updatePipelineStatus(3, 'loading', 'Analyzing match...');
        
        // Get Ollama config
        const config = await getOllamaConfig();
        
        // Extract keywords from JSON (if available)
        const jobKeywords = pipelineData.jobJson.keywords || [];
        const resumeKeywords = pipelineData.resumeJson.keywords || [];
        
        // Call API
        const response = await fetch('/api/ollama/resume-analysis', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                job_json: pipelineData.jobJson,
                resume_json: pipelineData.resumeJson,
                job_keywords: jobKeywords,
                resume_keywords: resumeKeywords,
                improved_resume: '',
                old_sim: 0.0,
                new_sim: 0.0,
                base_url: config.base_url,
                model: config.model
            })
        });
        
        const result = await response.json();
        
        if (response.ok && result.analysis_json) {
            updatePipelineStatus(3, 'success', 'Match analysis completed!');
            pipelineData.analysisJson = result.analysis_json; // Save for Step 4
            showPipelineResult(3, result.analysis_json);
            
            // Save analysis to history
            await saveAnalysisToHistory(currentAnalysisJobId, result.analysis_json);
        } else {
            updatePipelineStatus(3, 'error', result.error || 'Failed to generate analysis');
        }
    } catch (error) {
        console.error('Error in Step 3:', error);
        updatePipelineStatus(3, 'error', 'Error: ' + error.message);
    }
}

async function runStep4() {
    try {
        if (!pipelineData.resumeJson) {
            updatePipelineStatus(4, 'error', 'Please run Step 2 first');
            return;
        }
        
        updatePipelineStatus(4, 'loading', 'Improving resume...');
        
        // Get job description from current job
        const jobDetailsDiv = document.getElementById('job-details');
        const jobDescriptionEl = jobDetailsDiv?.querySelector('.job-description');
        const jobDescription = jobDescriptionEl?.textContent || '';
        
        if (!jobDescription) {
            updatePipelineStatus(4, 'error', 'No job description found');
            return;
        }
        
        // Get Ollama config
        const config = await getOllamaConfig();
        
        // Extract keywords
        const jobKeywords = pipelineData.jobJson?.keywords || [];
        const resumeKeywords = pipelineData.resumeJson?.keywords || [];
        
        // Get improvements from Step 3 if available
        const improvementsJson = pipelineData.analysisJson || null;
        
        // Backend will load resume from resume_path in config
        const response = await fetch('/api/ollama/resume-improvement', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                job_description: jobDescription,
                job_keywords: jobKeywords,
                resume: '', // Backend will load from resume_path in config
                resume_keywords: resumeKeywords,
                ats_recommendations: '',
                skill_priority_text: '',
                current_cosine_similarity: 0.0,
                improvements_json: improvementsJson, // Pass Step 3 analysis
                base_url: config.base_url,
                model: config.model
            })
        });
        
        const result = await response.json();
        
        if (response.ok && result.improved_resume) {
            updatePipelineStatus(4, 'success', 'Resume improvement examples generated!');
            // Step 4 now returns bullet point examples (string), not full resume
            showPipelineResult(4, result.improved_resume);
        } else {
            updatePipelineStatus(4, 'error', result.error || 'Failed to generate improvement examples');
        }
    } catch (error) {
        console.error('Error in Step 4:', error);
        updatePipelineStatus(4, 'error', 'Error: ' + error.message);
    }
}

async function saveAnalysisToHistory(jobId, analysisData) {
    try {
        const response = await fetch('/api/save-analysis', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                job_id: jobId,
                analysis_data: JSON.stringify(analysisData)
            })
        });
        
        if (!response.ok) {
            console.error('Failed to save analysis to history');
        }
    } catch (error) {
        console.error('Error saving analysis to history:', error);
    }
}

async function runFullAnalysis(jobId) {
    console.log('runFullAnalysis called with jobId:', jobId);
    const resumeSelector = document.getElementById('resume-selector');
    const modelSelector = document.getElementById('analysis-model-selector');
    const runButton = document.getElementById('run-full-analysis-btn');
    const progressDiv = document.getElementById('analysis-progress');
    const progressMessages = document.getElementById('progress-messages');
    const resultsDiv = document.getElementById('analysis-results');
    
    // Prevent double-execution
    if (runButton && runButton.disabled) {
        console.log('Analysis already running, ignoring duplicate call');
        return;
    }
    
    if (!resumeSelector || !resumeSelector.value) {
        alert('Please select a resume first');
        return;
    }
    
    if (!modelSelector || !modelSelector.value) {
        alert('Please select a model first');
        return;
    }
    
    const resumePath = resumeSelector.value;
    const selectedModel = modelSelector.value;
    
    // Disable button and show progress
    runButton.disabled = true;
    runButton.textContent = 'Running Analysis...';
    progressDiv.style.display = 'block';
    progressMessages.innerHTML = '';
    resultsDiv.style.display = 'none';
    
    // Clear previous results
    ['step1', 'step2', 'step3', 'step4'].forEach(function(step) {
        const resultEl = document.getElementById(step + '-result');
        const jsonEl = document.getElementById(step + '-json');
        if (resultEl) resultEl.style.display = 'none';
        if (jsonEl) jsonEl.textContent = '';
    });
    
    try {
        // Add initial message
        addProgressMessage('Starting full analysis pipeline...');
        addProgressMessage('Using model: ' + selectedModel);
        addProgressMessage('Resume: ' + resumeSelector.options[resumeSelector.selectedIndex].text);
        
        // Get Ollama config
        console.log('Getting Ollama config...');
        const config = await getOllamaConfig();
        console.log('Ollama config:', config);
        
        // Call the full analysis API
        console.log('Calling /api/run-full-analysis with:', {
            job_id: jobId,
            resume_path: resumePath,
            base_url: config.base_url,
            model: selectedModel
        });
        
        addProgressMessage('Sending request to server...');
        const response = await fetch('/api/run-full-analysis', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                job_id: jobId,
                resume_path: resumePath,
                base_url: config.base_url,
                model: selectedModel
            })
        });
        
        console.log('Response status:', response.status);
        addProgressMessage('Received response from server...');
        const result = await response.json();
        console.log('Response result:', result);
        
        if (response.ok && result.success) {
            // Display progress messages
            if (result.results && result.results.messages) {
                result.results.messages.forEach(function(msg) {
                    addProgressMessage(msg);
                });
            }
            
            // Display results
            if (result.results.step1) {
                console.log('Step 1 job JSON received:', result.results.step1);
                console.log('Step 1 job JSON keys:', Object.keys(result.results.step1 || {}));
                console.log('Step 1 job JSON title:', result.results.step1?.title);
                console.log('Step 1 job JSON company:', result.results.step1?.company);
                showPipelineResult(1, result.results.step1);
            }
            if (result.results.step2) {
                showPipelineResult(2, result.results.step2);
            }
            if (result.results.step3) {
                showPipelineResult(3, result.results.step3);
            }
            if (result.results.step4) {
                console.log('Step 4 data received:', result.results.step4);
                console.log('Step 4 overallFit:', result.results.step4?.overallFit);
                console.log('Step 4 overallFit.details:', result.results.step4?.overallFit?.details);
                console.log('Step 4 overallFit.commentary:', result.results.step4?.overallFit?.commentary);
                console.log('Step 4 improvements count:', result.results.step4?.improvements?.length || 0);
                console.log('Step 4 aspirationalImprovements count:', result.results.step4?.aspirationalImprovements?.length || 0);
                showPipelineResult(4, result.results.step4);
            }
            
            resultsDiv.style.display = 'block';
            addProgressMessage('✓ Analysis complete! Results displayed below.');
        } else {
            // Display messages in chronological order first, then show error
            if (result.results && result.results.messages) {
                result.results.messages.forEach(function(msg) {
                    addProgressMessage(msg);
                });
            }
            addProgressMessage('✗ Error: ' + (result.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error running full analysis:', error);
        console.error('Error stack:', error.stack);
        addProgressMessage('✗ Error: ' + error.message);
        if (error.message.includes('fetch')) {
            addProgressMessage('✗ Network error: Check if server is running and accessible');
        }
    } finally {
        runButton.disabled = false;
        runButton.textContent = 'Run Full Analysis';
    }
}

function addProgressMessage(message) {
    const progressMessages = document.getElementById('progress-messages');
    if (progressMessages) {
        const messageDiv = document.createElement('div');
        messageDiv.textContent = new Date().toLocaleTimeString() + ' - ' + message;
        messageDiv.style.marginBottom = '4px';
        progressMessages.appendChild(messageDiv);
        progressMessages.scrollTop = progressMessages.scrollHeight;
    }
}

function checkJobVisibilityWithFilters(jobItem, newSavedStatus) {
    /**
     * Check if a job should be visible with current filters after status change
     * Returns true if job should be visible, false if it should be hidden
     */
    // If no status filter is active, job should be visible
    if (selectedFilters.status.length === 0) {
        return true;
    }
    
    // Check if new status matches any active status filter
    const jobSaved = newSavedStatus === '1';
    const jobApplied = jobItem.getAttribute('data-applied') === '1';
    const jobInterview = jobItem.classList.contains('job-item-interview');
    const jobRejected = jobItem.classList.contains('job-item-rejected');
    
    for (let i = 0; i < selectedFilters.status.length; i++) {
        const status = selectedFilters.status[i];
        if (status === 'saved' && jobSaved) {
            return true;
        }
        if (status === 'applied' && jobApplied) {
            return true;
        }
        if (status === 'interview' && jobInterview) {
            return true;
        }
        if (status === 'rejected' && jobRejected) {
            return true;
        }
    }
    
    // No status matches, but we'll keep it visible anyway to avoid confusion
    return true;
}