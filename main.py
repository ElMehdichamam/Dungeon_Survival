"""main.py — entry point.  Run with:  python main.py"""

import pygame

from ui.menu import Menu
from game.core import Game


def main():
    while True:
        pygame.init()
        screen = pygame.display.set_mode((960, 640))

        action = Menu(screen).run()

        if action == "play":
            pygame.display.quit()
            result = Game().run()
            if result == "quit":
                break
        else:
            pygame.quit()
            break

    pygame.quit()


if __name__ == "__main__":
    main()
