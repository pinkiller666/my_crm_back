document.addEventListener('DOMContentLoaded', function () {
    const modeSelect = document.getElementById('id_mode');
    const alternatingBlock = document.querySelector('.field-days_off_at_start').closest('fieldset');
    const weekdayBlock = document.querySelector('.field-mon').closest('fieldset');

    function toggleBlocks() {
        const mode = modeSelect.value;
        if (mode === 'alternating') {
            alternatingBlock.style.display = '';
            weekdayBlock.style.display = 'none';
        } else if (mode === 'weekday') {
            alternatingBlock.style.display = 'none';
            weekdayBlock.style.display = '';
        }
    }

    if (modeSelect && alternatingBlock && weekdayBlock) {
        toggleBlocks(); // при загрузке страницы
        modeSelect.addEventListener('change', toggleBlocks);
    }
});
