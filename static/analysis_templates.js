/**
 * Analysis UI Templates
 * Centralized HTML templates for the analysis modal
 */

const AnalysisTemplates = {
    /**
     * Get the main analysis modal content structure
     */
    getModalContent: function() {
        return `
            <div class="ollama-pipeline-section">
                <div id="analysis-selectors" style="margin-bottom: 20px; padding: 15px; background-color: var(--bg-secondary); border-radius: 6px; border: 1px solid var(--border-color);">
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                        <div>
                            <label style="display: block; margin-bottom: 8px; font-weight: bold; color: var(--text-primary);">Select Resume:</label>
                            <select id="resume-selector" style="width: 100%; padding: 10px; border: 2px solid var(--accent-color); border-radius: 5px; font-size: 14px; background-color: var(--bg-primary); color: var(--text-primary);">
                            </select>
                        </div>
                        <div>
                            <label style="display: block; margin-bottom: 8px; font-weight: bold; color: var(--text-primary);">Select Model:</label>
                            <select id="analysis-model-selector" style="width: 100%; padding: 10px; border: 2px solid var(--accent-color); border-radius: 5px; font-size: 14px; background-color: var(--bg-primary); color: var(--text-primary);">
                            </select>
                        </div>
                    </div>
                </div>
                
                <div style="text-align: center; margin-bottom: 30px;">
                    <button class="pipeline-step-button" id="run-full-analysis-btn" style="padding: 15px 40px; font-size: 16px; font-weight: bold;">Run Full Analysis</button>
                </div>
                
                <div id="analysis-progress" style="margin-bottom: 20px; display: none;">
                    <h4 style="color: var(--accent-color); margin-bottom: 10px;">Progress:</h4>
                    <div id="progress-messages" style="background-color: var(--bg-secondary); padding: 15px; border-radius: 6px; max-height: 200px; overflow-y: auto; font-family: monospace; font-size: 13px; line-height: 1.6; color: var(--text-primary); border: 1px solid var(--border-color);">
                    </div>
                </div>
                
                <div id="analysis-results" style="display: none;">
                    ${this.getStep1Template()}
                    ${this.getStep2Template()}
                    ${this.getStep3Template()}
                    ${this.getStep4Template()}
                </div>
            </div>
        `;
    },

    /**
     * Step 1: Job JSON (collapsible)
     */
    getStep1Template: function() {
        return `
            <div class="pipeline-step">
                <div class="pipeline-step-header" style="cursor: pointer;" onclick="toggleStepResult('step1-result', 'step1-arrow')">
                    <span class="pipeline-step-title">Step 1: Job JSON</span>
                    <span id="step1-arrow" style="font-size: 18px; color: var(--text-tertiary); user-select: none; margin-left: 10px;">▼</span>
                </div>
                <div class="pipeline-result" id="step1-result" style="display: none;">
                    <div id="step1-json" style="padding: 20px;"></div>
                </div>
            </div>
        `;
    },

    /**
     * Step 2: Resume JSON (collapsible)
     */
    getStep2Template: function() {
        return `
            <div class="pipeline-step">
                <div class="pipeline-step-header" style="cursor: pointer;" onclick="toggleStepResult('step2-result', 'step2-arrow')">
                    <span class="pipeline-step-title">Step 2: Resume JSON</span>
                    <span id="step2-arrow" style="font-size: 18px; color: var(--text-tertiary); user-select: none; margin-left: 10px;">▼</span>
                </div>
                <div class="pipeline-result" id="step2-result" style="display: none;">
                    <div id="step2-json" style="padding: 20px;"></div>
                </div>
            </div>
        `;
    },

    /**
     * Step 3: Combined Keyword Analysis + Resume Improvements (always visible)
     */
    getStep3Template: function() {
        return `
            <div class="pipeline-step">
                <div class="pipeline-step-header">
                    <span class="pipeline-step-title">Step 3: Keyword Analysis</span>
                </div>
                <div class="pipeline-result" id="step3-result" style="display: none;">
                    <div id="step3-json" style="padding: 20px; color: var(--text-primary);"></div>
                </div>
            </div>
        `;
    },

    /**
     * Step 4: Resume Improvements (always visible)
     * Note: This is now combined with Step 3, but kept for backward compatibility
     */
    getStep4Template: function() {
        return `
            <div class="pipeline-step">
                <div class="pipeline-step-header">
                    <span class="pipeline-step-title">Step 4: Resume Improvements</span>
                </div>
                <div class="pipeline-result" id="step4-result" style="display: none;">
                    <div id="step4-json" style="padding: 20px; max-height: 600px; overflow-y: auto; color: var(--text-primary);"></div>
                </div>
            </div>
        `;
    },

    /**
     * Resume option for select dropdown
     */
    getResumeOption: function(resume) {
        return `<option value="${this.escapeHtml(resume.path)}">${this.escapeHtml(resume.name)}</option>`;
    },

    /**
     * Model option for select dropdown
     */
    getModelOption: function(model, isSelected = false) {
        const selected = isSelected ? ' selected' : '';
        return `<option value="${this.escapeHtml(model)}"${selected}>${this.escapeHtml(model)}</option>`;
    },

    /**
     * History step template (for analysis history modal)
     */
    getHistoryStepTemplate: function(stepNum, stepId, title, content) {
        if (stepNum === 1 || stepNum === 2) {
            // Collapsible steps
            return `
                <div class="pipeline-step" style="margin-bottom: 25px;">
                    <div class="pipeline-step-header" style="cursor: pointer;" onclick="toggleStepResult('${stepId}', '${stepId}-arrow')">
                        <span class="pipeline-step-title">${title}</span>
                        <span id="${stepId}-arrow" style="font-size: 18px; color: var(--text-tertiary); user-select: none; margin-left: 10px;">▼</span>
                    </div>
                    <div class="pipeline-result" id="${stepId}" style="display: none;">
                        <div style="padding: 20px;">${content}</div>
                    </div>
                </div>
            `;
        } else {
            // Always visible steps
            return `
                <div class="pipeline-step" style="margin-bottom: 25px;">
                    <div class="pipeline-step-header">
                        <span class="pipeline-step-title">${title}</span>
                    </div>
                    <div class="pipeline-result show">
                        <div style="padding: 20px;">${content}</div>
                    </div>
                </div>
            `;
        }
    },

    /**
     * Format job JSON data as HTML
     */
    formatJobJSON: function(job) {
        if (!job) return '<p style="color: var(--text-tertiary);">No job data available</p>';
        
        // Helper function to clean placeholder "string" values
        const cleanValue = (value) => {
            if (!value) return null;
            if (typeof value === 'string' && value.toLowerCase().trim() === 'string') {
                return null; // Treat "string" placeholder as empty
            }
            return value.trim() || null;
        };
        
        const parts = [];
        
        // Title and Company
        const title = cleanValue(job.title);
        const company = cleanValue(job.company);
        
        parts.push(`<div class="result-section" style="margin-bottom: 20px;">`);
        parts.push(`<h3 style="color: var(--accent-color); margin: 0 0 10px 0; font-size: 20px;">${this.escapeHtml(title || 'N/A')}</h3>`);
        parts.push(`<p style="color: var(--text-secondary); margin: 5px 0; font-size: 16px;"><strong>Company:</strong> ${this.escapeHtml(company || 'N/A')}</p>`);
        parts.push(`</div>`);
        
        // Key Details
        const location = cleanValue(job.location);
        const employmentType = cleanValue(job.employmentType);
        const salary = cleanValue(job.salary);
        const experience = cleanValue(job.experience);
        const education = cleanValue(job.education);
        
        parts.push(`<div class="result-section" style="background: var(--bg-secondary); padding: 15px; border-radius: 8px; margin-bottom: 20px; border: 1px solid var(--border-color);">`);
        if (location) parts.push(`<p style="margin: 5px 0;"><strong>📍 Location:</strong> ${this.escapeHtml(location)}</p>`);
        if (employmentType) parts.push(`<p style="margin: 5px 0;"><strong>💼 Type:</strong> ${this.escapeHtml(employmentType)}</p>`);
        if (salary) parts.push(`<p style="margin: 5px 0;"><strong>💰 Salary:</strong> ${this.escapeHtml(salary)}</p>`);
        if (experience) parts.push(`<p style="margin: 5px 0;"><strong>📊 Experience:</strong> ${this.escapeHtml(experience)}</p>`);
        if (education) parts.push(`<p style="margin: 5px 0;"><strong>🎓 Education:</strong> ${this.escapeHtml(education)}</p>`);
        parts.push(`</div>`);
        
        // Skills - filter out "string" placeholders
        if (job.skills && Array.isArray(job.skills) && job.skills.length > 0) {
            const validSkills = job.skills
                .filter(skill => skill && typeof skill === 'string' && skill.toLowerCase().trim() !== 'string')
                .map(skill => skill.trim())
                .filter(skill => skill.length > 0);
            
            if (validSkills.length > 0) {
                parts.push(`<div class="result-section" style="margin-bottom: 20px;">`);
                parts.push(`<h4 style="color: var(--text-primary); margin-bottom: 10px;">Skills Required:</h4>`);
                parts.push(`<div style="display: flex; flex-wrap: wrap; gap: 8px;">`);
                validSkills.forEach(skill => {
                    parts.push(`<span style="background: var(--accent-color); color: white; padding: 5px 12px; border-radius: 15px; font-size: 13px;">${this.escapeHtml(skill)}</span>`);
                });
                parts.push(`</div></div>`);
            }
        }
        
        // Requirements - filter out "string" placeholders
        if (job.requirements && Array.isArray(job.requirements) && job.requirements.length > 0) {
            const validRequirements = job.requirements
                .filter(req => req && typeof req === 'string' && req.toLowerCase().trim() !== 'string')
                .map(req => req.trim())
                .filter(req => req.length > 0);
            
            if (validRequirements.length > 0) {
                parts.push(`<div class="result-section" style="margin-bottom: 20px;">`);
                parts.push(`<h4 style="color: var(--text-primary); margin-bottom: 10px;">Requirements:</h4>`);
                parts.push(`<ul style="margin: 0; padding-left: 20px; line-height: 1.8;">`);
                validRequirements.forEach(req => {
                    parts.push(`<li style="margin-bottom: 8px; color: var(--text-secondary);">${this.escapeHtml(req)}</li>`);
                });
                parts.push(`</ul></div>`);
            }
        }
        
        // Description
        const description = cleanValue(job.description);
        if (description) {
            parts.push(`<div class="result-section" style="margin-bottom: 20px;">`);
            parts.push(`<h4 style="color: var(--text-primary); margin-bottom: 10px;">Description:</h4>`);
            parts.push(`<div style="color: var(--text-secondary); line-height: 1.6; max-height: 300px; overflow-y: auto; padding: 10px; background: var(--bg-secondary); border-radius: 5px; border: 1px solid var(--border-color);">${this.escapeHtml(description).replace(/\n/g, '<br>')}</div>`);
            parts.push(`</div>`);
        }
        
        return '<div class="formatted-result">' + parts.join('') + '</div>';
    },

    /**
     * Format resume JSON data as HTML
     */
    formatResumeJSON: function(resume) {
        if (!resume) return '<p style="color: var(--text-tertiary);">No resume data available</p>';
        
        const parts = [];
        
        // Personal Info
        if (resume.personalInfo) {
            parts.push(`<div class="result-section" style="background: var(--bg-secondary); padding: 15px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid var(--accent-color);">`);
            parts.push(`<h3 style="color: var(--accent-color); margin: 0 0 10px 0; font-size: 20px;">${this.escapeHtml(resume.personalInfo.name || 'N/A')}</h3>`);
            if (resume.personalInfo.title) parts.push(`<p style="margin: 5px 0; color: var(--text-secondary);"><strong>Title:</strong> ${this.escapeHtml(resume.personalInfo.title)}</p>`);
            if (resume.personalInfo.email) parts.push(`<p style="margin: 5px 0; color: var(--text-secondary);"><strong>Email:</strong> ${this.escapeHtml(resume.personalInfo.email)}</p>`);
            if (resume.personalInfo.phone) parts.push(`<p style="margin: 5px 0; color: var(--text-secondary);"><strong>Phone:</strong> ${this.escapeHtml(resume.personalInfo.phone)}</p>`);
            if (resume.personalInfo.address) parts.push(`<p style="margin: 5px 0; color: var(--text-secondary);"><strong>Location:</strong> ${this.escapeHtml(resume.personalInfo.address)}</p>`);
            parts.push(`</div>`);
        }
        
        // Career Summary
        if (resume.careerSummary) {
            parts.push(`<div class="result-section" style="margin-bottom: 20px;">`);
            parts.push(`<h4 style="color: var(--text-primary); margin-bottom: 10px;">Career Summary</h4>`);
            parts.push(`<p style="color: var(--text-secondary); line-height: 1.6;">${this.escapeHtml(resume.careerSummary)}</p>`);
            parts.push(`</div>`);
        }
        
        // Work Experience
        if (resume.workExperience && resume.workExperience.length > 0) {
            parts.push(`<div class="result-section" style="margin-bottom: 20px;">`);
            parts.push(`<h4 style="color: var(--text-primary); margin-bottom: 15px;">Work Experience</h4>`);
            resume.workExperience.forEach((exp) => {
                parts.push(`<div style="background: var(--bg-secondary); padding: 15px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid var(--accent-color); border: 1px solid var(--border-color);">`);
                parts.push(`<h5 style="color: var(--accent-color); margin: 0 0 5px 0; font-size: 16px;">${this.escapeHtml(exp.title || 'N/A')}</h5>`);
                parts.push(`<p style="margin: 5px 0; color: var(--text-secondary);"><strong>${this.escapeHtml(exp.company || 'N/A')}</strong>`);
                if (exp.location) parts.push(` - ${this.escapeHtml(exp.location)}`);
                parts.push(`</p>`);
                if (exp.dateStart || exp.dateEnd) {
                    parts.push(`<p style="margin: 5px 0; color: var(--text-tertiary); font-size: 13px;">`);
                    if (exp.dateStart) parts.push(`${this.escapeHtml(exp.dateStart)}`);
                    parts.push(` - `);
                    if (exp.dateEnd) parts.push(`${this.escapeHtml(exp.dateEnd)}`);
                    parts.push(`</p>`);
                }
                if (exp.description && exp.description.length > 0) {
                    parts.push(`<ul style="margin: 10px 0 0 0; padding-left: 20px; line-height: 1.6;">`);
                    exp.description.forEach(desc => {
                        parts.push(`<li style="margin-bottom: 5px; color: var(--text-secondary);">${this.escapeHtml(desc)}</li>`);
                    });
                    parts.push(`</ul>`);
                }
                parts.push(`</div>`);
            });
            parts.push(`</div>`);
        }
        
        // Education
        if (resume.education && resume.education.length > 0) {
            parts.push(`<div class="result-section" style="margin-bottom: 20px;">`);
            parts.push(`<h4 style="color: var(--text-primary); margin-bottom: 15px;">Education</h4>`);
            resume.education.forEach(edu => {
                parts.push(`<div style="background: var(--bg-secondary); padding: 15px; border-radius: 8px; margin-bottom: 10px; border: 1px solid var(--border-color);">`);
                parts.push(`<h5 style="color: var(--accent-color); margin: 0 0 5px 0; font-size: 16px;">${this.escapeHtml(edu.degree || 'N/A')}</h5>`);
                parts.push(`<p style="margin: 5px 0; color: var(--text-secondary);"><strong>${this.escapeHtml(edu.institution || 'N/A')}</strong>`);
                if (edu.location) parts.push(` - ${this.escapeHtml(edu.location)}`);
                parts.push(`</p>`);
                if (edu.gpa) parts.push(`<p style="margin: 5px 0; color: var(--text-tertiary);">GPA: ${this.escapeHtml(edu.gpa)}</p>`);
                if (edu.startDate || edu.endDate) {
                    parts.push(`<p style="margin: 5px 0; color: var(--text-tertiary); font-size: 13px;">`);
                    if (edu.startDate) parts.push(`${this.escapeHtml(edu.startDate)}`);
                    parts.push(` - `);
                    if (edu.endDate) parts.push(`${this.escapeHtml(edu.endDate)}`);
                    parts.push(`</p>`);
                }
                parts.push(`</div>`);
            });
            parts.push(`</div>`);
        }
        
        // Technical Skills
        if (resume.additional && resume.additional.technicalSkills && resume.additional.technicalSkills.length > 0) {
            parts.push(`<div class="result-section" style="margin-bottom: 20px;">`);
            parts.push(`<h4 style="color: var(--text-primary); margin-bottom: 10px;">Technical Skills</h4>`);
            parts.push(`<div style="display: flex; flex-wrap: wrap; gap: 8px;">`);
            resume.additional.technicalSkills.forEach(skill => {
                parts.push(`<span style="background: var(--accent-color); color: white; padding: 5px 12px; border-radius: 15px; font-size: 13px;">${this.escapeHtml(skill)}</span>`);
            });
            parts.push(`</div></div>`);
        }
        
        // Projects
        if (resume.projects && resume.projects.length > 0) {
            parts.push(`<div class="result-section" style="margin-bottom: 20px;">`);
            parts.push(`<h4 style="color: var(--text-primary); margin-bottom: 15px;">Projects</h4>`);
            resume.projects.forEach(project => {
                parts.push(`<div style="background: var(--bg-secondary); padding: 15px; border-radius: 8px; margin-bottom: 10px; border: 1px solid var(--border-color);">`);
                parts.push(`<h5 style="color: var(--accent-color); margin: 0 0 5px 0; font-size: 16px;">${this.escapeHtml(project.name || 'N/A')}</h5>`);
                if (project.description) parts.push(`<p style="margin: 5px 0; color: var(--text-secondary); line-height: 1.6;">${this.escapeHtml(project.description)}</p>`);
                if (project.technologies && project.technologies.length > 0) {
                    parts.push(`<div style="margin-top: 8px; display: flex; flex-wrap: wrap; gap: 6px;">`);
                    project.technologies.forEach(tech => {
                        parts.push(`<span style="background: var(--accent-color); color: white; padding: 3px 10px; border-radius: 12px; font-size: 12px;">${this.escapeHtml(tech)}</span>`);
                    });
                    parts.push(`</div>`);
                }
                parts.push(`</div>`);
            });
            parts.push(`</div>`);
        }
        
        return '<div class="formatted-result">' + parts.join('') + '</div>';
    },

    /**
     * Format match analysis data as HTML
     */
    formatMatchAnalysis: function(analysis) {
        // Step 3: ONLY keyword matching
        if (!analysis) return '<p style="color: var(--text-tertiary);">No keyword analysis data available</p>';
        
        const parts = [];
        
        // Keywords Analysis
        if (analysis.keywords) {
            const matching = analysis.keywords.matching || [];
            const missing = analysis.keywords.missing || [];
            
            parts.push(`<div class="result-section" style="margin-bottom: 25px;">`);
            parts.push(`<h4 style="color: var(--text-primary); margin: 0 0 15px 0; font-size: 18px;">🔑 Keyword Analysis</h4>`);
            
            if (matching.length > 0) {
                parts.push(`<div style="margin-bottom: 20px;">`);
                parts.push(`<div style="display: flex; align-items: center; margin-bottom: 10px;">`);
                parts.push(`<span style="background: var(--accent-color); color: white; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: bold; margin-right: 8px;">${matching.length}</span>`);
                parts.push(`<h5 style="margin: 0; color: var(--accent-color); font-size: 15px;">Matching Keywords</h5>`);
                parts.push(`</div>`);
                parts.push(`<div style="display: flex; flex-wrap: wrap; gap: 8px;">`);
                matching.forEach(keyword => {
                    parts.push(`<span style="background: var(--bg-secondary); color: var(--accent-color); padding: 6px 14px; border-radius: 16px; font-size: 13px; border: 1px solid var(--accent-color); font-weight: 500;">${this.escapeHtml(keyword)}</span>`);
                });
                parts.push(`</div></div>`);
            }
            
            if (missing.length > 0) {
                parts.push(`<div style="margin-bottom: 10px;">`);
                parts.push(`<div style="display: flex; align-items: center; margin-bottom: 10px;">`);
                parts.push(`<span style="background: var(--error-text); color: white; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: bold; margin-right: 8px;">${missing.length}</span>`);
                parts.push(`<h5 style="margin: 0; color: var(--error-text); font-size: 15px;">Missing Keywords</h5>`);
                parts.push(`</div>`);
                parts.push(`<div style="display: flex; flex-wrap: wrap; gap: 8px;">`);
                missing.forEach(keyword => {
                    parts.push(`<span style="background: var(--error-bg); color: var(--error-text); padding: 6px 14px; border-radius: 16px; font-size: 13px; border: 1px solid var(--error-text); font-weight: 500;">${this.escapeHtml(keyword)}</span>`);
                });
                parts.push(`</div></div>`);
            }
            
            if (matching.length > 0 || missing.length > 0) {
                const total = matching.length + missing.length;
                const matchPercent = total > 0 ? Math.round((matching.length / total) * 100) : 0;
                parts.push(`<div style="background: var(--bg-secondary); padding: 12px; border-radius: 6px; margin-top: 15px; border: 1px solid var(--border-color);">`);
                parts.push(`<p style="margin: 0; color: var(--text-secondary); font-size: 13px; line-height: 1.6;">`);
                parts.push(`<strong>Keyword Match Rate:</strong> ${matchPercent}% (${matching.length} of ${total} keywords found)`);
                parts.push(`</p></div>`);
            }
            
            parts.push(`</div>`);
        } else {
            parts.push(`<p style="color: var(--text-tertiary); font-style: italic;">No keyword data available.</p>`);
        }
        
        return parts.join('');
    },
    
    /**
     * Format improvements data as HTML (Step 4)
     */
    formatImprovements: function(analysis) {
        if (!analysis) return '<p style="color: var(--text-tertiary);">No improvements data available</p>';
        
        // Debug logging
        console.log('formatImprovements called with:', analysis);
        console.log('improvements array:', analysis.improvements);
        console.log('aspirationalImprovements array:', analysis.aspirationalImprovements);
        
        const parts = [];
        
        // Overall Fit - ALWAYS show this section
        const overallFit = analysis.overallFit || {};
        console.log('formatImprovements - overallFit object:', overallFit);
        console.log('formatImprovements - overallFit.details:', overallFit.details);
        console.log('formatImprovements - overallFit.commentary:', overallFit.commentary);
        const details = overallFit.details && String(overallFit.details).trim() ? String(overallFit.details).trim() : null;
        const commentary = overallFit.commentary && String(overallFit.commentary).trim() ? String(overallFit.commentary).trim() : null;
        console.log('formatImprovements - parsed details:', details);
        console.log('formatImprovements - parsed commentary:', commentary);
        
        // Always show the section, even if empty
        parts.push(`<div class="result-section" style="background: var(--info-bg); padding: 20px; border-radius: 8px; margin-bottom: 25px; border-left: 5px solid var(--info-text);">`);
        parts.push(`<h4 style="color: var(--info-text); margin: 0 0 15px 0; font-size: 18px;">📊 Overall Fit Assessment</h4>`);
        if (details) {
            parts.push(`<p style="color: var(--text-secondary); line-height: 1.8; margin-bottom: 15px;">${this.escapeHtml(details)}</p>`);
        } else {
            parts.push(`<p style="color: var(--text-tertiary); font-style: italic; margin-bottom: 15px;">Overall fit assessment is being generated. Please check back shortly.</p>`);
        }
        if (commentary) {
            parts.push(`<div style="background: var(--bg-primary); padding: 15px; border-radius: 5px; margin-top: 10px; border: 1px solid var(--border-color);">`);
            parts.push(`<p style="color: var(--text-primary); line-height: 1.8; margin: 0;"><strong>💡 Recommendation:</strong> ${this.escapeHtml(commentary)}</p>`);
            parts.push(`</div>`);
        }
        parts.push(`</div>`);
        
        // Improvements
        if (analysis.improvements && analysis.improvements.length > 0) {
            // Debug: log improvements to console
            console.log('Raw improvements:', JSON.stringify(analysis.improvements, null, 2));
            
            const filteredImprovements = analysis.improvements.filter(imp => {
                // Handle string improvements
                if (typeof imp === 'string') {
                    const lower = imp.toLowerCase();
                    return !lower.includes('summary') && 
                           !lower.includes('add a professional summary') &&
                           !lower.includes('add a summary') &&
                           !lower.includes('career summary') &&
                           !lower.includes('professional summary');
                }
                // Handle object improvements
                const section = (imp.section || '').toLowerCase();
                const suggestion = (imp.suggestion || '').toLowerCase();
                const example = (imp.example || '').toLowerCase();
                
                // Filter out summary-related suggestions
                const isSummaryRelated = section.includes('summary') || 
                                       suggestion.includes('add a professional summary') ||
                                       suggestion.includes('add a summary') ||
                                       suggestion.includes('career summary') ||
                                       suggestion.includes('professional summary');
                
                // Don't filter out improvements that have examples, even if suggestion is vague
                // Only filter if it's summary-related OR if it's vague AND has no example
                if (isSummaryRelated) {
                    return false;
                }
                
                // If no example and suggestion is vague, still show it but it will show a warning
                return true;
            });
            
            console.log('Filtered improvements:', filteredImprovements.length);
            
            if (filteredImprovements.length > 0) {
                const improvementsId = 'improvements-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
                parts.push(`<div class="result-section" style="margin-bottom: 20px;">`);
                parts.push(`<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; cursor: pointer;" onclick="toggleImprovements('${improvementsId}')">`);
                parts.push(`<h4 style="color: var(--text-primary); margin: 0; font-size: 18px;">✨ Suggested Improvements (${filteredImprovements.length})</h4>`);
                parts.push(`<span id="${improvementsId}-arrow" style="font-size: 20px; color: var(--text-tertiary); user-select: none;">▼</span>`);
                parts.push(`</div>`);
                // Show improvements by default (not hidden)
                parts.push(`<div id="${improvementsId}" style="display: block;">`);
                filteredImprovements.forEach((improvement, idx) => {
                    // Handle case where improvement might be a string
                    if (typeof improvement === 'string') {
                        parts.push(`<div style="background: var(--bg-secondary); padding: 15px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid var(--accent-color); border: 1px solid var(--border-color);">`);
                        parts.push(`<div style="display: flex; align-items: start;">`);
                        parts.push(`<span style="background: var(--accent-color); color: white; width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; margin-right: 12px; flex-shrink: 0; font-size: 16px;">${idx + 1}</span>`);
                        parts.push(`<div style="flex: 1;">`);
                        parts.push(`<p style="margin: 0; color: var(--text-secondary); line-height: 1.7;">${this.escapeHtml(improvement)}</p>`);
                        parts.push(`</div></div></div>`);
                        return;
                    }
                    
                    // Extract fields, handling null/undefined/empty strings
                    const section = improvement.section && String(improvement.section).trim() ? String(improvement.section).trim() : null;
                    const suggestion = improvement.suggestion && String(improvement.suggestion).trim() ? String(improvement.suggestion).trim() : null;
                    const example = improvement.example && String(improvement.example).trim() ? String(improvement.example).trim() : null;
                    
                    // Skip if improvement has no content at all
                    if (!section && !suggestion && !example) {
                        return; // Skip empty improvements
                    }
                    
                    // Don't skip vague suggestions - show them with a warning if no example
                    
                    parts.push(`<div style="background: var(--bg-secondary); padding: 15px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid var(--accent-color); border: 1px solid var(--border-color);">`);
                    parts.push(`<div style="display: flex; align-items: start;">`);
                    parts.push(`<span style="background: var(--accent-color); color: white; width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; margin-right: 12px; flex-shrink: 0; font-size: 16px;">${idx + 1}</span>`);
                    parts.push(`<div style="flex: 1;">`);
                    if (section) {
                        parts.push(`<p style="margin: 0 0 8px 0; color: var(--accent-color); font-weight: bold; font-size: 15px;">${this.escapeHtml(section)}</p>`);
                    }
                    if (suggestion) {
                        parts.push(`<p style="margin: 0 0 10px 0; color: var(--text-secondary); line-height: 1.7;">${this.escapeHtml(suggestion)}</p>`);
                    }
                    if (example) {
                        parts.push(`<div style="background: var(--bg-primary); padding: 15px; border-radius: 5px; margin-top: 12px; border-left: 4px solid var(--accent-color); border: 1px solid var(--border-color);">`);
                        parts.push(`<p style="margin: 0 0 10px 0; color: var(--accent-color); font-weight: 600; font-size: 14px;">✨ Ready-to-Use Example:</p>`);
                        parts.push(`<p style="margin: 0; color: var(--text-primary); line-height: 1.7; font-size: 15px; font-weight: 500;">${this.escapeHtml(example)}</p>`);
                        parts.push(`</div>`);
                    } else if (suggestion) {
                        // If no example provided, show a warning
                        parts.push(`<div style="background: var(--bg-tertiary); padding: 12px; border-radius: 5px; margin-top: 10px; border-left: 3px solid var(--accent-color); border: 1px solid var(--border-color);">`);
                        parts.push(`<p style="margin: 0; color: var(--text-tertiary); font-size: 13px; font-style: italic;">⚠️ No example provided. This suggestion needs a complete rewritten bullet point.</p>`);
                        parts.push(`</div>`);
                    }
                    parts.push(`</div></div></div>`);
                });
                parts.push(`</div></div>`);
            }
        }
        
        // Aspirational Improvements (hypothetical/fictional)
        if (analysis.aspirationalImprovements && analysis.aspirationalImprovements.length > 0) {
            const aspirationalId = 'aspirational-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
            parts.push(`<div class="result-section" style="margin-bottom: 20px; margin-top: 30px;">`);
            parts.push(`<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; cursor: pointer;" onclick="toggleImprovements('${aspirationalId}')">`);
            parts.push(`<h4 style="color: var(--text-primary); margin: 0; font-size: 18px;">💭 If You Had This Experience (${analysis.aspirationalImprovements.length})</h4>`);
            parts.push(`<span id="${aspirationalId}-arrow" style="font-size: 20px; color: var(--text-tertiary); user-select: none;">▼</span>`);
            parts.push(`</div>`);
            parts.push(`<div style="background: var(--bg-tertiary); padding: 15px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid var(--accent-color); border: 1px solid var(--border-color);">`);
            parts.push(`<p style="margin: 0 0 15px 0; color: var(--text-tertiary); font-size: 14px; font-style: italic;">⚠️ These are hypothetical suggestions for experience you don't currently have. They show what you COULD add if you had this experience.</p>`);
            parts.push(`</div>`);
            parts.push(`<div id="${aspirationalId}" style="display: block;">`);
            analysis.aspirationalImprovements.forEach((improvement, idx) => {
                const suggestion = improvement.suggestion && String(improvement.suggestion).trim() ? String(improvement.suggestion).trim() : null;
                const example = improvement.example && String(improvement.example).trim() ? String(improvement.example).trim() : null;
                
                if (!suggestion && !example) {
                    return; // Skip empty
                }
                
                parts.push(`<div style="background: var(--bg-tertiary); padding: 15px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid var(--accent-color); border: 1px solid var(--border-color);">`);
                parts.push(`<div style="display: flex; align-items: start;">`);
                parts.push(`<span style="background: var(--accent-color); color: white; width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; margin-right: 12px; flex-shrink: 0; font-size: 16px;">${idx + 1}</span>`);
                parts.push(`<div style="flex: 1;">`);
                if (suggestion) {
                    parts.push(`<p style="margin: 0 0 10px 0; color: var(--text-secondary); line-height: 1.7; font-weight: 500;">${this.escapeHtml(suggestion)}</p>`);
                }
                if (example) {
                    parts.push(`<div style="background: var(--bg-primary); padding: 15px; border-radius: 5px; margin-top: 12px; border-left: 4px solid var(--accent-color); border: 1px solid var(--border-color);">`);
                    parts.push(`<p style="margin: 0 0 10px 0; color: var(--accent-color); font-weight: 600; font-size: 14px;">💡 Example (if you had this experience):</p>`);
                    parts.push(`<p style="margin: 0; color: var(--text-primary); line-height: 1.7; font-size: 15px; font-weight: 500;">${this.escapeHtml(example)}</p>`);
                    parts.push(`</div>`);
                }
                parts.push(`</div></div></div>`);
            });
            parts.push(`</div></div>`);
        }
        
        return '<div class="formatted-result">' + parts.join('') + '</div>';
    },

    /**
     * Format resume improvement text as HTML
     */
    formatResumeImprovement: function(text) {
        if (!text) return '<p style="color: var(--text-tertiary);">No improvement examples available</p>';
        
        const parts = ['<div class="formatted-result" style="font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.7;">'];
        const lines = text.split('\n');
        let inList = false;
        let inNumberedList = false;
        
        lines.forEach((line, idx) => {
            const trimmed = line.trim();
            
            // Check for numbered list items (1., 2., etc.)
            const numberedMatch = trimmed.match(/^(\d+)\.\s+(.+)$/);
            if (numberedMatch) {
                if (inList) { parts.push('</ul>'); inList = false; }
                if (!inNumberedList) { 
                    parts.push('<ol style="margin: 15px 0; padding-left: 30px; line-height: 1.8;">'); 
                    inNumberedList = true; 
                }
                parts.push(`<li style="margin-bottom: 12px; color: var(--text-secondary); padding-left: 5px;">${this.escapeHtml(numberedMatch[2])}</li>`);
                return;
            }
            
            if (trimmed.startsWith('### ')) {
                if (inList) { parts.push('</ul>'); inList = false; }
                if (inNumberedList) { parts.push('</ol>'); inNumberedList = false; }
                parts.push(`<li style="margin-bottom: 12px; color: var(--text-secondary); padding-left: 5px;">${this.escapeHtml(numberedMatch[2])}</li>`);
            }
            
            if (trimmed.startsWith('### ')) {
                if (inList) { parts.push('</ul>'); inList = false; }
                if (inNumberedList) { parts.push('</ol>'); inNumberedList = false; }
                parts.push(`<h3 style="color: var(--accent-color); margin: 25px 0 15px 0; font-size: 18px; border-bottom: 2px solid var(--border-color); padding-bottom: 8px;">${this.escapeHtml(trimmed.substring(4))}</h3>`);
            } else if (trimmed.startsWith('## ')) {
                if (inList) { parts.push('</ul>'); inList = false; }
                if (inNumberedList) { parts.push('</ol>'); inNumberedList = false; }
                parts.push(`<h2 style="color: var(--accent-color); margin: 30px 0 20px 0; font-size: 22px;">${this.escapeHtml(trimmed.substring(3))}</h2>`);
            } else if (trimmed.startsWith('# ')) {
                if (inList) { parts.push('</ul>'); inList = false; }
                if (inNumberedList) { parts.push('</ol>'); inNumberedList = false; }
                parts.push(`<h1 style="color: var(--accent-color); margin: 30px 0 20px 0; font-size: 26px;">${this.escapeHtml(trimmed.substring(2))}</h1>`);
            } else if (trimmed === '---' || trimmed === '***') {
                if (inList) { parts.push('</ul>'); inList = false; }
                if (inNumberedList) { parts.push('</ol>'); inNumberedList = false; }
                parts.push(`<hr style="border: none; border-top: 2px solid var(--border-color); margin: 20px 0;">`);
            } else if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
                if (inNumberedList) { parts.push('</ol>'); inNumberedList = false; }
                if (!inList) { parts.push('<ul style="margin: 10px 0; padding-left: 25px; line-height: 1.8;">'); inList = true; }
                parts.push(`<li style="margin-bottom: 8px; color: var(--text-secondary);">${this.escapeHtml(trimmed.substring(2))}</li>`);
            } else if (trimmed.includes('**')) {
                if (inList) { parts.push('</ul>'); inList = false; }
                if (inNumberedList) { parts.push('</ol>'); inNumberedList = false; }
                let processed = trimmed.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                parts.push(`<p style="margin: 10px 0; color: var(--text-secondary);">${processed}</p>`);
            } else if (trimmed.length > 0) {
                if (inList) { parts.push('</ul>'); inList = false; }
                if (inNumberedList) { parts.push('</ol>'); inNumberedList = false; }
                parts.push(`<p style="margin: 10px 0; color: var(--text-secondary);">${this.escapeHtml(trimmed)}</p>`);
            } else {
                if (inList) { parts.push('</ul>'); inList = false; }
                if (inNumberedList) { parts.push('</ol>'); inNumberedList = false; }
                if (idx < lines.length - 1) parts.push('<br>');
            }
        });
        
        if (inList) parts.push('</ul>');
        if (inNumberedList) parts.push('</ol>');
        parts.push('</div>');
        return parts.join('');
    },

    /**
     * Format job details HTML
     */
    formatJobDetails: function(job) {
        const parts = [];
        parts.push(`<h2 class="job-title">${this.escapeHtml(job.title)}</h2>`);
        parts.push(`<div class="button-container" style="display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; margin-bottom: 15px;">`);
        
        // Primary actions (always visible)
        parts.push(`<a href="${this.escapeHtml(job.job_url)}" class="job-button" target="_blank" rel="noopener noreferrer">Go to job</a>`);
        parts.push(`<button class="job-button" onclick="markAsCoverLetter(${job.id})">Cover Letter</button>`);
        parts.push(`<button class="job-button" onclick="generateProjects(${job.id})">Generate Projects</button>`);
        
        // Dropdown menu for other actions
        parts.push(`<div class="job-actions-dropdown" style="position: relative; display: inline-block;">`);
        parts.push(`<button class="job-button" onclick="toggleActionsDropdown(${job.id})" style="display: flex; align-items: center; gap: 5px;">Actions ▼</button>`);
        parts.push(`<div id="actions-dropdown-${job.id}" class="actions-dropdown-menu" style="display: none; position: absolute; top: 100%; left: 0; background-color: var(--bg-primary); border: 2px solid var(--accent-color); border-radius: 5px; min-width: 200px; z-index: 1000; margin-top: 5px; box-shadow: 0 4px 8px var(--shadow);">`);
        parts.push(`<button class="dropdown-action-btn" id="applied-btn-${job.id}" onclick="toggleApplied(${job.id}); closeActionsDropdown(${job.id});">${job.applied == 1 ? '✓ Unmark Applied' : 'Mark Applied'}</button>`);
        parts.push(`<button class="dropdown-action-btn" id="rejected-btn-${job.id}" onclick="toggleRejected(${job.id}); closeActionsDropdown(${job.id});">${job.rejected == 1 ? '✓ Unmark Rejected' : 'Mark Rejected'}</button>`);
        parts.push(`<button class="dropdown-action-btn" id="interview-btn-${job.id}" onclick="toggleInterview(${job.id}); closeActionsDropdown(${job.id});">${job.interview == 1 ? '✓ Unmark Interview' : 'Mark Interview'}</button>`);
        parts.push(`<button class="dropdown-action-btn" id="save-btn-${job.id}" onclick="toggleSaved(${job.id}); closeActionsDropdown(${job.id});">${job.saved == 1 ? '✓ Unsave' : 'Save'}</button>`);
        if (job.hidden == 1) {
            parts.push(`<button class="dropdown-action-btn" onclick="unhideJob(${job.id}); closeActionsDropdown(${job.id});">Unhide</button>`);
        } else {
            parts.push(`<button class="dropdown-action-btn" onclick="hideJob(${job.id}); closeActionsDropdown(${job.id});">Hide</button>`);
        }
        parts.push(`<button class="dropdown-action-btn" onclick="openAnalysisModal(${job.id}); closeActionsDropdown(${job.id});">AI Analysis</button>`);
        parts.push(`<button class="dropdown-action-btn" onclick="openAnalysisHistory(${job.id}); closeActionsDropdown(${job.id});">Analysis History</button>`);
        parts.push(`</div></div>`);
        
        parts.push(`</div>`);
        parts.push(`<p class="job-detail">${this.escapeHtml(job.company)}, ${this.escapeHtml(job.location)}</p>`);
        parts.push(`<p class="job-detail">${this.escapeHtml(job.date)}</p>`);
        parts.push(`<p class="job-description">${this.escapeHtml(job.job_description)}</p>`);
        
        return parts.join('');
    },

    /**
     * Format analysis history entry
     */
    formatHistoryEntry: function(analysis, index, total) {
        const parts = [];
        parts.push('<div class="pipeline-step" style="border-left: 4px solid #4CAF50;">');
        parts.push('<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">');
        parts.push(`<span style="font-weight: bold; color: var(--accent-color);">Analysis #${total - index}</span>`);
        parts.push(`<span style="color: var(--text-tertiary); font-size: 0.9em;">${new Date(analysis.created_at).toLocaleString()}</span>`);
        parts.push('</div>');
        return parts.join('');
    },

    /**
     * Format history entry footer
     */
    formatHistoryEntryFooter: function() {
        return '</div>';
    },

    /**
     * Format history container
     */
    formatHistoryContainer: function() {
        return '<div style="display: flex; flex-direction: column; gap: 15px;">';
    },

    /**
     * Format history container footer
     */
    formatHistoryContainerFooter: function() {
        return '</div>';
    },

    /**
     * Format error message for history
     */
    formatHistoryError: function(message) {
        return `<p style="text-align: center; color: var(--error-text); padding: 40px;">Error loading analysis history: ${this.escapeHtml(message)}</p>`;
    },

    /**
     * Format empty history message
     */
    formatHistoryEmpty: function() {
        return '<p style="text-align: center; color: var(--text-tertiary); padding: 40px;">No analysis history found for this job.</p>';
    },

    /**
     * Format raw JSON fallback for history
     */
    formatHistoryRawJSON: function(data) {
        return `<div class="pipeline-result show"><pre style="max-height: 300px;">${this.escapeHtml(data)}</pre></div>`;
    },

    /**
     * Format single analysis result wrapper
     */
    formatSingleAnalysisWrapper: function(content) {
        return `<div class="pipeline-result show"><div style="padding: 20px;">${content}</div></div>`;
    },

    /**
     * Format JSON fallback
     */
    formatJSONFallback: function(data) {
        return `<pre style="background: var(--bg-secondary); padding: 15px; border-radius: 5px; overflow-x: auto; color: var(--text-primary); border: 1px solid var(--border-color);">${this.escapeHtml(JSON.stringify(data, null, 2))}</pre>`;
    },

    /**
     * Helper to escape HTML
     */
    escapeHtml: function(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};

