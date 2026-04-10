# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a single-file Tic-Tac-Toe game implementation (`tictactoe.html`) with a beach/pixel-art visual theme. The game features a 4x4 grid, score tracking, and animated background elements.

## Development Workflow

- **Running the game**: Open `tictactoe.html` directly in any modern web browser
- **Development**: Edit `tictactoe.html` and refresh the browser to see changes
- **Version control**: Use `git commit` and `git push origin main` to sync with GitHub
- **Repository**: https://github.com/chenlisenyuan-ship-it/autoarm

## Architecture

The entire application is contained in `tictactoe.html`:

- **HTML structure**: Game board, score panel, and decorative background elements
- **CSS**: All styles are inline, including:
  - Pixel-art beach scene with animated ocean, fish, birds, and palm trees
  - Game UI with retro-inspired borders and shadows
  - Responsive flexbox layout for the game container
- **JavaScript**: Game logic includes:
  - 4x4 board state management
  - Win detection for horizontal, vertical, and diagonal lines (4 in a row)
  - Score persistence across games
  - Winner highlighting animation

Key JavaScript variables and functions:
- `current`: Tracks whose turn it is ('X' or 'O')
- `cells`: Array of DOM elements representing board cells
- `wins`: Array of win condition index combinations
- `createBoard()`: Initializes/resets the 4x4 grid
- `handleClick(i)`: Processes player moves
- `checkWin()`: Tests all win conditions
- `reset()`: Starts a new game

## File Structure

- `tictactoe.html` - The complete game (HTML, CSS, JavaScript)
- `README.md` - Basic project documentation
- `.gitignore` - Excludes IDE files and Claude session data

## Notes

- No build system, package manager, or external dependencies
- The game uses inline event handlers (`onclick`) and DOM manipulation
- CSS includes complex pixel-art created with `box-shadow` properties
- GitHub repository is configured with SSH remote: `git@github.com:chenlisenyuan-ship-it/autoarm.git`