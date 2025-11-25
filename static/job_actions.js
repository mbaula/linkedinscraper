var selectedJob = null;

// Multi-select filter state
let selectedFilters = {
    city: [],
    title: [],
    company: [],
    status: []
};

// Search and filter functionality
document.addEventListener('DOMContentLoaded', function() {
    const searchBar = document.getElementById('search-bar');
    const sortBy = document.getElementById('sort-by');
    const filterDate = document.getElementById('filter-date');
    
    // Check if search was completed and refresh if needed
    checkForSearchCompletion();
    
    // Populate filter dropdowns with unique values
    populateFilters();
    
    // Add event listeners
    if (searchBar) {
        searchBar.addEventListener('input', applyAllFilters);
    }
    if (sortBy) {
        sortBy.addEventListener('change', applyAllFilters);
    }
    if (filterDate) {
        filterDate.addEventListener('change', applyAllFilters);
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

function populateFilters() {
    const jobItems = document.querySelectorAll('.job-item');
    const cities = new Set();
    const titles = new Set();
    const companies = new Set();
    
    jobItems.forEach(function(jobItem) {
        const city = jobItem.getAttribute('data-city');
        const title = jobItem.getAttribute('data-title');
        const company = jobItem.getAttribute('data-company');
        
        if (city) cities.add(city);
        if (title) titles.add(title);
        if (company) companies.add(company);
    });
    
    // Populate city filter
    populateMultiSelect('city', Array.from(cities).sort());
    
    // Populate title filter
    populateMultiSelect('title', Array.from(titles).sort());
    
    // Populate company filter
    populateMultiSelect('company', Array.from(companies).sort());
}

function populateMultiSelect(type, options) {
    const optionsContainer = document.getElementById(`${type}-options`);
    optionsContainer.innerHTML = '';
    
    options.forEach(function(option) {
        const div = document.createElement('div');
        div.className = 'multi-select-option';
        const safeId = `${type}-${option.replace(/[^a-zA-Z0-9]/g, '_')}_${Math.random().toString(36).substr(2, 9)}`;
        const escapedValue = option.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
        
        div.innerHTML = `
            <input type="checkbox" id="${safeId}" value="${escapedValue}" onchange="toggleFilter('${type}', this.value)">
            <label for="${safeId}" style="cursor: pointer; flex: 1;">${option}</label>
        `;
        optionsContainer.appendChild(div);
    });
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

function toggleFilter(type, value) {
    // Decode HTML entities
    const decodedValue = value.replace(/&quot;/g, '"').replace(/&#39;/g, "'");
    const index = selectedFilters[type].indexOf(decodedValue);
    if (index > -1) {
        selectedFilters[type].splice(index, 1);
    } else {
        selectedFilters[type].push(decodedValue);
    }
    
    // Update checkbox state for status filter
    if (type === 'status') {
        const checkbox = document.getElementById(`filter-status-${decodedValue}`);
        if (checkbox) {
            checkbox.checked = index === -1;
        }
    }
    
    updateFilterDisplay(type);
    applyAllFilters();
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
    const searchTerm = document.getElementById('search-bar').value.toLowerCase();
    const sortBy = document.getElementById('sort-by').value;
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
        
        // Apply status filter (saved, applied, interview, rejected)
        if (shouldShow && selectedFilters.status.length > 0) {
            const jobSaved = jobItem.getAttribute('data-saved') === '1';
            const jobApplied = jobItem.getAttribute('data-applied') === '1';
            const jobInterview = jobItem.classList.contains('job-item-interview');
            const jobRejected = jobItem.classList.contains('job-item-rejected');
            
            let matchesStatus = false;
            for (let i = 0; i < selectedFilters.status.length; i++) {
                const status = selectedFilters.status[i];
                if (status === 'saved' && jobSaved) {
                    matchesStatus = true;
                    break;
                }
                if (status === 'applied' && jobApplied) {
                    matchesStatus = true;
                    break;
                }
                if (status === 'interview' && jobInterview) {
                    matchesStatus = true;
                    break;
                }
                if (status === 'rejected' && jobRejected) {
                    matchesStatus = true;
                    break;
                }
            }
            
            if (!matchesStatus) {
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
    
    // Sort the visible jobs
    if (sortBy && visibleJobs.length > 0) {
        sortJobs(visibleJobs, sortBy);
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
    if (selectedJob !== null) {
        selectedJob.classList.remove('job-item-selected');
    }
    console.log('Showing job details: ' + jobId); 
    var newSelectedJob = document.querySelector(`.job-item[data-job-id="${jobId}"]`);
    newSelectedJob.classList.add('job-item-selected');
    selectedJob = newSelectedJob;

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
    var html = '<h2 class="job-title">' + job.title + '</h2>';
    html += '<div class="button-container" style="text-align:center">';
    html += '<a href="' + job.job_url + '" class="job-button" target="_blank" rel="noopener noreferrer">Go to job</a>';
    html += '<button class="job-button" onclick="markAsCoverLetter(' + job.id + ')">Cover Letter</button>';
    html += '<button class="job-button" onclick="markAsApplied(' + job.id + ')">Applied</button>';
    html += '<button class="job-button" onclick="markAsRejected(' + job.id + ')">Rejected</button>';
    html += '<button class="job-button" onclick="markAsInterview(' + job.id + ')">Interview</button>';
    html += '<button class="job-button" id="save-btn-' + job.id + '" onclick="toggleSaved(' + job.id + ')">' + (job.saved ? 'Unsave' : 'Save') + '</button>';
    html += '<button class="job-button" onclick="hideJob(' + job.id + ')">Hide</button>';
    html += '<button class="job-button" onclick="openAnalysisModal(' + job.id + ')">AI Analysis</button>';
    html += '<button class="job-button" onclick="openAnalysisHistory(' + job.id + ')">Analysis History</button>';
    html += '</div>';
    html += '<p class="job-detail">' + job.company + ', ' + job.location + '</p>';
    html += '<p class="job-detail">' + job.date + '</p>';
    html += '<p class="job-description">' + job.job_description + '</p>';

    jobDetailsDiv.innerHTML = html;
    
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


function markAsApplied(jobId) {
    console.log('Marking job as applied: ' + jobId)
    fetch('/mark_applied/' + jobId, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            console.log(data);  // Log the response
            if (data.success) {
                var jobCard = document.querySelector(`.job-item[data-job-id="${jobId}"]`);
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
        });
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

function markAsRejected(jobId) {
    console.log('Marking job as rejected: ' + jobId)
    fetch('/mark_rejected/' + jobId, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            console.log(data);  // Log the response
            if (data.success) {
                var jobCard = document.querySelector(`.job-item[data-job-id="${jobId}"]`);
                jobCard.classList.add('job-item-rejected');
            }
        });
}

function hideJob(jobId) {
    fetch('/hide_job/' + jobId, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                var jobCard = document.querySelector(`.job-item[data-job-id="${jobId}"]`);
                
                // Find the next sibling in the DOM that is a job-item
                var nextJobCard = jobCard.nextElementSibling;
                while(nextJobCard && !nextJobCard.classList.contains('job-item')) {
                    nextJobCard = nextJobCard.nextElementSibling;
                }
                
                // If a next job exists, show its details
                if (nextJobCard) {
                    var nextJobId = nextJobCard.getAttribute('data-job-id');
                    showJobDetails(nextJobId);
                }
                
                // Hide the current job
                jobCard.style.display = 'none'; // Or you can remove it from DOM entirely

                // If no next job exists, clear the job details div
                if (!nextJobCard) {
                    var jobDetailsDiv = document.getElementById('job-details');
                    jobDetailsDiv.innerHTML = '';
                }
            }
        });
}


function markAsInterview(jobId) {
    console.log('Marking job as interview: ' + jobId)
    fetch('/mark_interview/' + jobId, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            console.log(data);  // Log the response
            if (data.success) {
                var jobCard = document.querySelector(`.job-item[data-job-id="${jobId}"]`);
                jobCard.classList.add('job-item-interview');
            }
        });
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
                // Reapply filters to update display
                applyAllFilters();
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

function showPipelineResult(step, data) {
    const resultEl = document.getElementById(`step${step}-result`);
    const jsonEl = document.getElementById(`step${step}-json`);
    if (resultEl && jsonEl) {
        if (typeof data === 'string') {
            // For Step 4 (improved resume), it's just text
            jsonEl.textContent = data;
        } else {
            jsonEl.textContent = JSON.stringify(data, null, 2);
        }
        resultEl.style.display = 'block';
        resultEl.classList.add('show');
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
    
    // Load available resumes
    let resumeOptions = '<option value="">Loading resumes...</option>';
    try {
        const resumeResponse = await fetch('/api/list-resumes');
        const resumeData = await resumeResponse.json();
        if (resumeData.resumes && resumeData.resumes.length > 0) {
            resumeOptions = '<option value="">Select a resume...</option>';
            resumeData.resumes.forEach(function(resume) {
                resumeOptions += '<option value="' + resume.path + '">' + resume.name + '</option>';
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
            const configResponse = await fetch('/api/config');
            const config = await configResponse.json();
            const defaultModel = config.ollama_model || modelData.models[0];
            
            modelOptions = '';
            modelData.models.forEach(function(model) {
                const selected = model === defaultModel ? ' selected' : '';
                modelOptions += '<option value="' + model + '"' + selected + '>' + model + '</option>';
            });
        } else {
            modelOptions = '<option value="">No models available</option>';
        }
    } catch (error) {
        console.error('Error loading models:', error);
        modelOptions = '<option value="">Error loading models</option>';
    }
    
    // Build pipeline UI
    let html = '<div class="ollama-pipeline-section">';
    
    // Resume selector and Model selector
    html += '<div style="margin-bottom: 20px; padding: 15px; background-color: #f8f9fa; border-radius: 6px;">';
    html += '<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">';
    html += '<div>';
    html += '<label style="display: block; margin-bottom: 8px; font-weight: bold; color: #333;">Select Resume:</label>';
    html += '<select id="resume-selector" style="width: 100%; padding: 10px; border: 2px solid #4CAF50; border-radius: 5px; font-size: 14px; background-color: white;">';
    html += resumeOptions;
    html += '</select>';
    html += '</div>';
    html += '<div>';
    html += '<label style="display: block; margin-bottom: 8px; font-weight: bold; color: #333;">Select Model:</label>';
    html += '<select id="analysis-model-selector" style="width: 100%; padding: 10px; border: 2px solid #4CAF50; border-radius: 5px; font-size: 14px; background-color: white;">';
    html += modelOptions;
    html += '</select>';
    html += '</div>';
    html += '</div>';
    html += '</div>';
    
    // Single Run Button
    html += '<div style="text-align: center; margin-bottom: 30px;">';
    html += '<button class="pipeline-step-button" onclick="runFullAnalysis(' + jobId + ')" id="run-full-analysis-btn" style="padding: 15px 40px; font-size: 16px; font-weight: bold;">Run Full Analysis</button>';
    html += '</div>';
    
    // Verbose output area
    html += '<div id="analysis-progress" style="margin-bottom: 20px; display: none;">';
    html += '<h4 style="color: #4CAF50; margin-bottom: 10px;">Progress:</h4>';
    html += '<div id="progress-messages" style="background-color: #f8f9fa; padding: 15px; border-radius: 6px; max-height: 200px; overflow-y: auto; font-family: monospace; font-size: 13px; line-height: 1.6;">';
    html += '</div>';
    html += '</div>';
    
    // Results display
    html += '<div id="analysis-results" style="display: none;">';
    
    // Step 1: Job Posting → Job JSON
    html += '<div class="pipeline-step">';
    html += '<div class="pipeline-step-header">';
    html += '<span class="pipeline-step-title">Step 1: Job JSON</span>';
    html += '</div>';
    html += '<div class="pipeline-result" id="step1-result" style="display: none;"><pre id="step1-json"></pre></div>';
    html += '</div>';
    
    // Step 2: Resume Text → Resume JSON
    html += '<div class="pipeline-step">';
    html += '<div class="pipeline-step-header">';
    html += '<span class="pipeline-step-title">Step 2: Resume JSON</span>';
    html += '</div>';
    html += '<div class="pipeline-result" id="step2-result" style="display: none;"><pre id="step2-json"></pre></div>';
    html += '</div>';
    
    // Step 3: Job JSON + Resume JSON → Match Analysis
    html += '<div class="pipeline-step">';
    html += '<div class="pipeline-step-header">';
    html += '<span class="pipeline-step-title">Step 3: Match Analysis</span>';
    html += '</div>';
    html += '<div class="pipeline-result" id="step3-result" style="display: none;"><pre id="step3-json"></pre></div>';
    html += '</div>';
    
    // Step 4: Resume Rewriter (Optional)
    html += '<div class="pipeline-step">';
    html += '<div class="pipeline-step-header">';
    html += '<span class="pipeline-step-title">Step 4: Resume Improvement</span>';
    html += '</div>';
    html += '<div class="pipeline-result" id="step4-result" style="display: none;"><pre id="step4-json"></pre></div>';
    html += '</div>';
    
    html += '</div>'; // Close analysis-results
    html += '</div>'; // Close ollama-pipeline-section
    
    modalContent.innerHTML = html;
    modal.style.display = 'block';
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
            let html = '<div style="display: flex; flex-direction: column; gap: 15px;">';
            data.analyses.forEach(function(analysis, index) {
                html += '<div class="pipeline-step" style="border-left: 4px solid #4CAF50;">';
                html += '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">';
                html += '<span style="font-weight: bold; color: #4CAF50;">Analysis #' + (data.analyses.length - index) + '</span>';
                html += '<span style="color: #666; font-size: 0.9em;">' + new Date(analysis.created_at).toLocaleString() + '</span>';
                html += '</div>';
                html += '<div class="pipeline-result show"><pre style="max-height: 300px;">' + JSON.stringify(JSON.parse(analysis.analysis_data), null, 2) + '</pre></div>';
                html += '</div>';
            });
            html += '</div>';
            modalContent.innerHTML = html;
        } else {
            modalContent.innerHTML = '<p style="text-align: center; color: #666; padding: 40px;">No analysis history found for this job.</p>';
        }
    } catch (error) {
        console.error('Error fetching analysis history:', error);
        modalContent.innerHTML = '<p style="text-align: center; color: #d32f2f; padding: 40px;">Error loading analysis history: ' + error.message + '</p>';
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
                base_url: config.base_url,
                model: config.model
            })
        });
        
        const result = await response.json();
        
        if (response.ok && result.improved_resume) {
            updatePipelineStatus(4, 'success', 'Resume improvement completed!');
            showPipelineResult(4, { improved_resume: result.improved_resume });
        } else {
            updatePipelineStatus(4, 'error', result.error || 'Failed to improve resume');
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
    const resumeSelector = document.getElementById('resume-selector');
    const modelSelector = document.getElementById('analysis-model-selector');
    const runButton = document.getElementById('run-full-analysis-btn');
    const progressDiv = document.getElementById('analysis-progress');
    const progressMessages = document.getElementById('progress-messages');
    const resultsDiv = document.getElementById('analysis-results');
    
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
        // Get Ollama config
        const config = await getOllamaConfig();
        
        // Add initial message
        addProgressMessage('Starting full analysis pipeline...');
        addProgressMessage('Using model: ' + selectedModel);
        addProgressMessage('Resume: ' + resumeSelector.options[resumeSelector.selectedIndex].text);
        
        // Call the full analysis API
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
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            // Display progress messages
            if (result.results && result.results.messages) {
                result.results.messages.forEach(function(msg) {
                    addProgressMessage(msg);
                });
            }
            
            // Display results
            if (result.results.step1) {
                showPipelineResult(1, result.results.step1);
            }
            if (result.results.step2) {
                showPipelineResult(2, result.results.step2);
            }
            if (result.results.step3) {
                showPipelineResult(3, result.results.step3);
            }
            if (result.results.step4) {
                showPipelineResult(4, result.results.step4);
            }
            
            resultsDiv.style.display = 'block';
            addProgressMessage('✓ Analysis complete! Results displayed below.');
        } else {
            addProgressMessage('✗ Error: ' + (result.error || 'Unknown error'));
            if (result.results && result.results.messages) {
                result.results.messages.forEach(function(msg) {
                    addProgressMessage(msg);
                });
            }
        }
    } catch (error) {
        console.error('Error running full analysis:', error);
        addProgressMessage('✗ Error: ' + error.message);
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