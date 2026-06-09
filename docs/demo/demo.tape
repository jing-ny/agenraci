# VHS tape — renders docs/demo/demo.gif (https://github.com/charmbracelet/vhs)
#
# Render from the repo root, with agenraci installed:
#   pip install -e .
#   vhs docs/demo/demo.tape
#
# Produces docs/demo/demo.gif, which the README embeds near the top.

Output docs/demo/demo.gif

Set Shell "bash"
Set FontSize 18
Set Width 1100
Set Height 720
Set Padding 20
Set Theme "Dracula"

Type "# A charter where two roles are both 'accountable' for shipping code."
Enter
Sleep 1500ms
Type "agenraci validate docs/demo/charter-broken.yaml"
Enter
Sleep 3500ms

Type "# R1 caught the conflict. Fix it: exactly one accountable."
Enter
Sleep 1500ms
Type "agenraci validate docs/demo/charter-fixed.yaml"
Enter
Sleep 3500ms

Type "# PASS — a valid operating constitution."
Enter
Sleep 2500ms
