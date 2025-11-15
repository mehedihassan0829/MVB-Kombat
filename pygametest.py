import pygame
import sys
import time

# Initialize pygame
pygame.init()

# Create a simple window
screen = pygame.display.set_mode((400, 300))
pygame.display.set_caption("Pygame Test")

# Fill screen with a color
screen.fill((0, 128, 255))
pygame.display.flip()

# Keep window open for 2 seconds or until closed
start = time.time()
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
    if time.time() - start > 2:
        running = False

pygame.quit()
sys.exit()

## IF THIS RUNS AND THE BLUE SCREEN APPEARS, PYGAME IS WORKING