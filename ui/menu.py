import pygame


BG_COLOR = (12, 10, 16)
GOLD     = (240, 210, 80)
WHITE    = (255, 255, 255)
DIM      = (140, 140, 170)
RED      = (220, 60, 60)


class Menu:
    def __init__(self, screen):
        self.screen = screen
        self.font_title = pygame.font.Font(None, 80)
        self.font_sub   = pygame.font.Font(None, 36)
        self.font_body  = pygame.font.Font(None, 24)
        self.clock = pygame.time.Clock()
        self.w, self.h = screen.get_size()

    def _center(self, surf, y_offset):
        rect = surf.get_rect(center=(self.w // 2, self.h // 2 + y_offset))
        self.screen.blit(surf, rect)

    def _text(self, font, text, color, y):
        surf = font.render(text, True, color)
        self._center(surf, y)

    def title_screen(self):
        while True:
            dt = self.clock.tick(60)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit"
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        return "play"
                    if event.key == pygame.K_c:
                        return "credits"
                    if event.key == pygame.K_ESCAPE:
                        return "quit"

            self.screen.fill(BG_COLOR)
            self._text(self.font_title, "Dungeon Survival", GOLD, -80)
            self._text(self.font_sub,   "The Game", WHITE, -30)
            self._text(self.font_body,  "[Enter]  Start Game", DIM, 60)
            self._text(self.font_body,  "[C]      Credits",    DIM, 100)
            self._text(self.font_body,  "[Esc]    Quit",       DIM, 140)

            scroll = (pygame.time.get_ticks() // 40) % (self.w + 200)
            for i in range(5):
                x = (scroll + i * (self.w // 4)) % (self.w + 200) - 100
                pygame.draw.circle(self.screen, (30, 25, 40), (x, 20), 3)

            pygame.display.flip()

    def credits_screen(self):
        lines = [
            ("Dungeon Survival", GOLD, -100),
            ("", None, -70),
            ("A roguelike dungeon crawler", WHITE, -40),
            ("", None, -10),
            ("Development & Design", DIM, 20),
            ("Mehdi", WHITE, 55),
            ("Chamam Marouane", WHITE, 85),
            ("Bnouanas Bilal", WHITE, 115),
            ("Grimah Zakaria", WHITE, 145),
            ("Nacerdine", WHITE, 175),
            ("", None, 205),
            ("Powered by Pygame & pytmx", DIM, 225),
            ("", None, 255),
            ("[Enter]  Back to Title", DIM, 285),
        ]
        while True:
            self.clock.tick(60)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit"
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                        return "title"
            self.screen.fill(BG_COLOR)
            for text, color, y in lines:
                if text:
                    self._text(self.font_body if color == DIM else
                               self.font_sub if color == WHITE else
                               self.font_title, text, color, y)
            pygame.display.flip()

    def run(self):
        while True:
            result = self.title_screen()
            if result == "play":
                return "play"
            if result == "quit":
                return "quit"
            if result == "credits":
                result = self.credits_screen()
                if result == "quit":
                    return "quit"
