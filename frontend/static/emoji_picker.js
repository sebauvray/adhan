/* === Reusable emoji picker ===
 *
 * Usage:
 *   <button class="emoji-pick-btn" id="my-btn">🙂</button>
 *   <div class="emoji-picker" id="my-picker" style="display:none"></div>
 *   <script>
 *     attachEmojiPicker(
 *       document.getElementById('my-btn'),
 *       document.getElementById('my-picker'),
 *       (emoji) => { ... }
 *     );
 *   </script>
 *
 * The button shows the current emoji; clicking it toggles the picker.
 * Selecting an emoji updates the button text, closes the picker, and
 * fires onSelect(emoji).
 */

const EMOJI_PICKER_LIST = [
  '😀','😃','😄','😁','😆','😅','🤣','😂','🙂','😊',
  '😇','🥰','😍','🤩','😎','🤓','🧐','🤠','🥳','😏',
  '😺','🐶','🐱','🦁','🐯','🐻','🐼','🐸','🐵','🦊',
  '🦄','🐝','🦋','🐢','🐙','🦈','🐬','🦅','🦉','🐧',
  '🌟','⭐','🌙','☀️','🔥','💧','❄️','🌈','🍀','🌸',
  '🏀','⚽','🎯','🎮','🎸','🎨','📚','💻','🚀','✈️',
  '👨','👩','👦','👧','👶','🧔','👳','👲','🧕','👼',
];

function attachEmojiPicker(buttonEl, pickerEl, onSelect) {
  if (!buttonEl || !pickerEl) return;

  buttonEl.addEventListener('click', (e) => {
    e.preventDefault();
    const isOpen = pickerEl.dataset.openFor === buttonEl.id || pickerEl.dataset.openFor === '__attached__';
    if (isOpen && pickerEl.style.display !== 'none') {
      pickerEl.style.display = 'none';
      pickerEl.dataset.openFor = '';
      return;
    }
    pickerEl.dataset.openFor = buttonEl.id || '__attached__';
    pickerEl.innerHTML = EMOJI_PICKER_LIST.map(emoji =>
      `<button type="button" class="emoji-option" data-emoji="${emoji}">${emoji}</button>`
    ).join('');
    pickerEl.querySelectorAll('.emoji-option').forEach(opt => {
      opt.addEventListener('click', () => {
        const emoji = opt.dataset.emoji;
        buttonEl.textContent = emoji;
        pickerEl.style.display = 'none';
        pickerEl.dataset.openFor = '';
        if (typeof onSelect === 'function') onSelect(emoji);
      });
    });
    pickerEl.style.display = 'grid';
  });
}
