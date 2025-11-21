var selectedJob = null;

// Multi-select filter state
let selectedFilters = {
    city: [],
    title: [],
    company: []
};

// Search and filter functionality
document.addEventListener('DOMContentLoaded', function() {
    const searchBar = document.getElementById('search-bar');
    const sortBy = document.getElementById('sort-by');
    
    // Populate filter dropdowns with unique values
    populateFilters();
    
    // Add event listeners
    if (searchBar) {
        searchBar.addEventListener('input', applyAllFilters);
    }
    if (sortBy) {
        sortBy.addEventListener('change', applyAllFilters);
    }
    
    // Close dropdowns when clicking outside
    document.addEventListener('click', function(event) {
        if (!event.target.closest('.multi-select')) {
            closeAllDropdowns();
        }
    });
});

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
        // Focus search input
        setTimeout(() => {
            document.getElementById(`${type}-search`).focus();
        }, 10);
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
    
    updateFilterDisplay(type);
    applyAllFilters();
}

function updateFilterDisplay(type) {
    const count = selectedFilters[type].length;
    const countElement = document.getElementById(`${type}-count`);
    
    if (count === 0) {
        countElement.textContent = `All ${type === 'city' ? 'Cities' : type === 'title' ? 'Job Titles' : 'Companies'}`;
    } else {
        countElement.textContent = `${count} selected`;
    }
}

function applyAllFilters() {
    const searchTerm = document.getElementById('search-bar').value.toLowerCase();
    const sortBy = document.getElementById('sort-by').value;
    
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
    var coverLetterPane = document.getElementById('cover-letter-pane');
    // Check if the coverLetterPane exists
    if (coverLetterPane) {
        // Check if cover letter exists
        if (coverLetter === null) {
            coverLetterPane.innerText = 'No cover letter exists for this job.';
        } else {
            coverLetterPane.innerText = coverLetter;
        }
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
    html += '<button class="job-button" onclick="hideJob(' + job.id + ')">Hide</button>';
    html += '</div>';
    html += '<p class="job-detail">' + job.company + ', ' + job.location + '</p>';
    html += '<p class="job-detail">' + job.date + '</p>';
    html += '<p class="job-description">' + job.job_description + '</p>';

    jobDetailsDiv.innerHTML = html;
    if (job.cover_letter) {
        // Update the cover letter div
        coverLetterDiv.innerHTML = '<p class="job-description">' + job.cover_letter + '</p>';
    } else {
        // Clear the cover letter div if no cover letter exists
        coverLetterDiv.innerHTML = '';
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

function markAsCoverLetter(jobId) {
    console.log('Marking job as cover letter: ' + jobId)
    fetch('/get_CoverLetter/' + jobId, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            console.log(data);  // Log the response
            if (data.cover_letter) {
                // Show the job details again, this will also update the cover letter
                showJobDetails(jobId);
            }
        });
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