/**
 * FSM Cascade Widget JavaScript
 *
 * Handles cascading dropdown behavior for hierarchical status codes.
 * Each dropdown filters the next based on the selected value.
 */

(function() {
    'use strict';

    /**
     * Initialize a cascade widget instance.
     *
     * @param {HTMLElement} container - The widget container element
     */
    function initCascadeWidget(container) {
        const hierarchy = JSON.parse(container.dataset.hierarchy || '{}');
        const separator = container.dataset.separator || '-';
        const levels = parseInt(container.dataset.levels || '2', 10);
        const hiddenInput = container.querySelector('input[type="hidden"]');
        const selects = container.querySelectorAll('select[data-level]');

        if (!hiddenInput || selects.length === 0) {
            console.warn('FSMCascadeWidget: Missing required elements');
            return;
        }

        /**
         * Get choices for a level based on parent selections.
         *
         * @param {number} level - The level index (0-based)
         * @param {string[]} parentValues - Values selected in parent levels
         * @returns {Array<{value: string, label: string}>} Choices for this level
         */
        function getChoicesForLevel(level, parentValues) {
            let current = hierarchy;

            // Navigate to the correct position in hierarchy
            for (let i = 0; i < level; i++) {
                const val = parentValues[i];
                if (val && current[val]) {
                    current = current[val];
                } else {
                    return [];
                }
            }

            // Extract choices (skip __label__ and __value__ keys)
            const choices = [];
            for (const [key, val] of Object.entries(current)) {
                if (key.startsWith('__')) continue;
                const label = (typeof val === 'object' && val.__label__) ? val.__label__ : key;
                choices.push({ value: key, label: label });
            }

            // Sort by label
            choices.sort((a, b) => a.label.localeCompare(b.label));
            return choices;
        }

        /**
         * Update a select element with new choices.
         *
         * @param {HTMLSelectElement} select - The select element to update
         * @param {Array<{value: string, label: string}>} choices - New choices
         * @param {string} [selectedValue] - Value to select (optional)
         */
        function updateSelect(select, choices, selectedValue) {
            // Store current selection if no explicit selection given
            const currentValue = selectedValue !== undefined ? selectedValue : select.value;

            // Clear existing options (except placeholder)
            select.innerHTML = '';

            // Add placeholder option
            const placeholder = document.createElement('option');
            placeholder.value = '';
            placeholder.textContent = '-- Select --';
            select.appendChild(placeholder);

            // Add choices
            for (const choice of choices) {
                const option = document.createElement('option');
                option.value = choice.value;
                option.textContent = choice.label;
                if (choice.value === currentValue) {
                    option.selected = true;
                }
                select.appendChild(option);
            }

            // Enable/disable based on whether there are choices
            select.disabled = choices.length === 0;
        }

        /**
         * Update the hidden input with the combined value.
         */
        function updateHiddenValue() {
            const parts = [];
            for (const select of selects) {
                const val = select.value;
                if (val) {
                    parts.push(val);
                }
            }

            // Only set value if all levels are selected
            if (parts.length === levels) {
                hiddenInput.value = parts.join(separator);
            } else {
                hiddenInput.value = '';
            }

            // Trigger change event on hidden input
            hiddenInput.dispatchEvent(new Event('change', { bubbles: true }));
        }

        /**
         * Handle change on a select element.
         *
         * @param {Event} event - The change event
         */
        function handleSelectChange(event) {
            const changedSelect = event.target;
            const changedLevel = parseInt(changedSelect.dataset.level, 10);

            // Get current values up to and including changed level
            const parentValues = [];
            for (let i = 0; i <= changedLevel; i++) {
                parentValues.push(selects[i].value);
            }

            // Update all subsequent levels
            for (let i = changedLevel + 1; i < levels; i++) {
                const choices = getChoicesForLevel(i, parentValues);
                updateSelect(selects[i], choices);
                parentValues.push(selects[i].value);
            }

            updateHiddenValue();
        }

        // Attach change handlers to all selects
        for (const select of selects) {
            select.addEventListener('change', handleSelectChange);
        }

        // Initialize hidden value from current selections
        updateHiddenValue();
    }

    /**
     * Initialize all cascade widgets on the page.
     */
    function initAllWidgets() {
        const containers = document.querySelectorAll('.fsm-cascade-widget');
        for (const container of containers) {
            if (!container.dataset.initialized) {
                initCascadeWidget(container);
                container.dataset.initialized = 'true';
            }
        }
    }

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAllWidgets);
    } else {
        initAllWidgets();
    }

    // Re-initialize when new content is added (for dynamic admin inlines)
    if (typeof django !== 'undefined' && django.jQuery) {
        django.jQuery(document).on('formset:added', function() {
            initAllWidgets();
        });
    }

    // Export for manual initialization
    window.FSMCascadeWidget = {
        init: initCascadeWidget,
        initAll: initAllWidgets
    };
})();
