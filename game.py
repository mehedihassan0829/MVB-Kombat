import pygame
import random
from sys import exit

#region GAME PROPERTIES AND DEBUG

# SCREEN DIMENSIONS AND DEBUG

SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 576
FPS = 60 # game fps
DISPLAY_HITBOXES = False

pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
clock = pygame.time.Clock()

current_game = None
current_menu = None
callbacks = []

#endregion

# SPRITES AND ANIMATION

ANIMATION_LATENCY = 10 # every ANIMATION_LATENCY frames, change animation frame
X_OFFSET = 20

# DIRECTIONS

RIGHT = 1
LEFT = -1

# COLOUR DEFS

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 255)
ORANGE = (250, 164, 5)
GREEN = (5, 250, 9)
GRAY = (120, 120, 120)

# ANIMATION STATES

class AnimatedSprite(object):
    def __init__(self, name, spritesheet, length):
        self.name = name
        self.spritesheet = spritesheet
        self.length = length

IDLE = AnimatedSprite("IDLE", "assets/spritesheet_idle.png", 4)
PUNCHING = AnimatedSprite("PUNCHING", "assets/spritesheet_punch.png", 4)
KICKING = AnimatedSprite("KICKING", "assets/spritesheet_kick.png", 4)
JUMPING = AnimatedSprite("JUMPING", "assets/spritesheet_jump.png", 1)
FLINCHING = AnimatedSprite("FLINCHING", "assets/spritesheet_flinch.png", 3)

DUMMY_IDLE = AnimatedSprite("IDLE", "assets/dummy_draft.png", 1)
DUMMY_FLINCHING = AnimatedSprite("FLINCHING", "assets/dummy_draft.png", 1)

DEFAULT_CHARACTER = [IDLE, PUNCHING, KICKING, JUMPING, FLINCHING]
DUMMY_CHARACTER = [DUMMY_IDLE, DUMMY_FLINCHING]

# FONT AND TEXT

FONT_SIZE = 16
FONTFACE = "Consolas"

font = pygame.font.SysFont(FONTFACE, FONT_SIZE)

screen.fill(WHITE) # change bg color to white
pygame.display.set_caption("My game") # changes title of game

GRAVITY = 1

# PLAYER MODIFIABLE ATTRIBUTES

PLAYER_SPEED = 7
PLAYER_JUMPSPEED = -18
PLAYER_SPRITE_HEIGHT = 128
PLAYER_SPRITE_WIDTH = 128
PLAYER_HEALTH = 100

PLAYER_HITBOX_WIDTH = 50
PLAYER_HITBOX_HEIGHT = 60

ground_y = (SCREEN_HEIGHT + PLAYER_SPRITE_HEIGHT) / 2

PLAYER1_SPAWN_POSITION = ((SCREEN_WIDTH + PLAYER_SPRITE_WIDTH) / 3, ground_y)
PLAYER1_KEYLEFT = pygame.K_a
PLAYER1_KEYRIGHT = pygame.K_d
PLAYER1_KEYJUMP = pygame.K_w
PLAYER1_KEYDUCK = pygame.K_s
PLAYER1_KEYPUNCH = pygame.K_j
PLAYER1_KEYKICK = pygame.K_k

PLAYER2_SPAWN_POSITION = (2 * (SCREEN_WIDTH + PLAYER_SPRITE_WIDTH) / 3, ground_y)
PLAYER2_KEYLEFT = pygame.K_LEFT
PLAYER2_KEYRIGHT = pygame.K_RIGHT
PLAYER2_KEYJUMP = pygame.K_UP
PLAYER2_KEYDUCK = pygame.K_DOWN
PLAYER2_KEYPUNCH = pygame.K_PERIOD
PLAYER2_KEYKICK = pygame.K_SLASH

NO_KEY = pygame.K_UNKNOWN

class Hitbox(object):
    def __init__(self, surface, player):
        self.player_ref = player
        self.surface_ref = surface
        self.image = pygame.Surface((PLAYER_HITBOX_WIDTH, PLAYER_HITBOX_HEIGHT))
        if (DISPLAY_HITBOXES): self.image.fill(RED)
        self.rect = self.image.get_rect()
        self.rect.center = self.player_ref.rect.center

    def update(self):
        # sort out these magic constants
        self.rect.x = self.player_ref.rect.x + 10
        self.rect.y = self.player_ref.rect.y + 45
        if (self.player_ref.direction_facing == LEFT):
            self.rect.x += 60

    def draw(self):
        self.surface_ref.blit(self.image, self.rect) # draw to screen

class Player(pygame.sprite.Sprite):
    def __init__(self, surface, key_left, key_right, key_jump, key_duck, key_punch, key_kick, spawn_position, direction, healthbar_offset, sprites, game, health, display_healthbar, tutorial):
        super().__init__()
        
        # other attributes
        self.surface_ref = surface
        self.opponent_ref = None
        self.opponent_hitbox_ref = None
        self.game_ref = game
        self.tutorial_ref = tutorial

        # gameplay
        self.frozen = False
        self.health = health
        self.display_healthbar = display_healthbar
        self.direction_facing = direction
        self.is_jumping = False
        self.is_ducking = False
        self.speed = PLAYER_SPEED
        self.vertical_velocity = 0

        self.punched = False
        self.kicked = False

        self.key_left = key_left
        self.key_right = key_right
        self.key_jump = key_jump
        self.key_duck = key_duck
        self.key_punch = key_punch
        self.key_kick = key_kick

        self.spawn_position = spawn_position

        # animations
        self.sprite_handler = SpriteHandler(self, ANIMATION_LATENCY, self.game_ref)
        self.load_sprites(sprites)
        
        self.image = pygame.Surface((PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
        self.rect = self.image.get_rect()
        self.rect.center = self.spawn_position
        self.rect.y = ground_y - PLAYER_HITBOX_HEIGHT # ground player

        self.go_idle()

        if (not self.display_healthbar): healthbar_offset = (-100, -100)
        self.healthbar = HealthBar(self.health, self.surface_ref, healthbar_offset)

        self.ignoring_platforms = False
    
    def reset_position(self):
        self.rect.center = self.spawn_position
        self.rect.y = ground_y - PLAYER_HITBOX_HEIGHT # ground player

    def unignore_platforms(self):
        self.ignoring_platforms = False

    def load_sprites(self, sprites):
        for sprite in sprites:
            spritesheet = Spritesheet(sprite.spritesheet)
            self.sprite_handler.add_anim(sprite.name, spritesheet.load_image_strip((0, 0, 64, 64), sprite.length))

    def update(self):
        global current_game
        if (not current_game): return

        self.healthbar.update(f"{self.health}", self.health) # update healthbar

        keystate = pygame.key.get_pressed()

        # JUMPING ANF FALLING
        grounded = self.check_grounded()

        # if not jumping and not grounded, start falling
        if (not self.is_jumping) and (not self.is_ducking) and (not grounded):
            self.vertical_velocity = 0
            self.is_jumping = True
            # doubles as a falling animation
            self.current_animation = "JUMPING"
            if (not self.sprite_handler.anims.get(self.current_animation)): return
            self.sprite_handler.update_sprite(self.current_animation)

        if (self.is_jumping or self.vertical_velocity != 0):
            self.vertical_velocity += GRAVITY
            self.rect.y += self.vertical_velocity

            if (self.vertical_velocity >= 0) and not self.ignoring_platforms:
                for obj in self.game_ref.interactable_game_objects:
                    if (self.rect.colliderect(obj.rect)):
                        if (self.rect.bottom - self.vertical_velocity <= obj.rect.top): # dont fall into object
                            self.rect.bottom = obj.rect.top
                            self.is_jumping = False
                            self.vertical_velocity = 0
                            self.go_idle()
                            return

            if (self.rect.y >= (ground_y - PLAYER_HITBOX_HEIGHT) and (self.vertical_velocity >= 0)):
                self.rect.y = (ground_y - PLAYER_HITBOX_HEIGHT)
                self.is_jumping = False
                self.vertical_velocity = 0
                self.go_idle()

        # OTHER PLAYER ACTIONS

        if self.frozen: return # do nothing if frozen

        # move based on key input
        if keystate[self.key_left]:
            if (self.direction_facing == RIGHT):
                # we have switched directions
                self.image = pygame.transform.flip(self.image, 1, 0)
                self.rect.move_ip(-X_OFFSET, 0)
            self.rect.move_ip(-self.get_move_left(), 0)
            if (self.tutorial_ref): 
                self.tutorial_ref.do_tutorial()
                self.tutorial_ref.has_moved = True
        if keystate[self.key_right]:
            if (self.direction_facing == LEFT):
                # we have switched directions
                self.image = pygame.transform.flip(self.image, 1, 0)
                self.rect.move_ip(X_OFFSET, 0)
            self.rect.move_ip(self.get_move_right(), 0)
            if (self.tutorial_ref): 
                self.tutorial_ref.do_tutorial()
                self.tutorial_ref.has_moved = True

        # can only duck or jump if on ground
        # fall through platform if both pressed at same time
        if keystate[self.key_jump] and (not self.is_ducking) and (not self.is_jumping):
            self.jump()
            if (self.tutorial_ref): 
                self.tutorial_ref.do_tutorial()
                self.tutorial_ref.has_jumped = True
        elif keystate[self.key_duck] and (not self.is_ducking) and (not self.is_jumping):
            self.fall_through()

        # attacks
        if keystate[self.key_punch] and (not self.is_ducking) and (not self.punched) and (not self.kicked):
            self.punch_attack()
            if (self.tutorial_ref): 
                self.tutorial_ref.do_tutorial()
                self.tutorial_ref.has_punched = True
        if keystate[self.key_kick] and (not self.is_ducking) and (not self.kicked) and (not self.punched):
            self.kick_attack()
            if (self.tutorial_ref): 
                self.tutorial_ref.do_tutorial()
                self.tutorial_ref.has_kicked = True

    def check_grounded(self):
        if (self.rect.y >= (ground_y - PLAYER_HITBOX_HEIGHT)): # if standind on the main ground 
            return True
        
        self.rect.y += 1
        grounded = False
        for obj in self.game_ref.interactable_game_objects:
            if (self.rect.colliderect(obj.rect) and (obj.rect.top >= self.rect.bottom - 1)): # if colliding with any platforms, is grounded
                grounded = True
                break

        self.rect.y -= 1
        return grounded

    def get_move_left(self):
        self.direction_facing = LEFT
        if (self.rect.x < self.speed): return self.rect.x
        else: return self.speed 

    def get_move_right(self):
        self.direction_facing = RIGHT
        if ((SCREEN_WIDTH - PLAYER_SPRITE_WIDTH) - self.rect.x < self.speed): return (SCREEN_WIDTH - PLAYER_SPRITE_WIDTH) - self.rect.x
        else: return self.speed

    def go_idle(self):
        self.current_animation = "IDLE"
        self.sprite_handler.update_sprite(self.current_animation)

    def attach_opponent(self, opponent, opponent_hitbox):
        self.opponent_ref = opponent
        self.opponent_hitbox_ref = opponent_hitbox

    def unpunch(self):
        self.punched = False

    def punch_attack(self):
        # freeze for 1/2 second
        self.punched = True
        Callback(self.unpunch, PUNCHING.length * ANIMATION_LATENCY + 5)

        # do punch attack
        attack = PunchAttack(self, self.opponent_hitbox_ref, self.direction_facing, self.surface_ref, self.game_ref)
        self.game_ref.attacks.append(attack)

        repeat = Repeat(attack.follow_player, 1)
        Callback(repeat.kill, PUNCHING.length * ANIMATION_LATENCY)

        self.do_animation_and_reset("PUNCHING")

    def unkick(self):
        self.kicked = False

    def kick_attack(self):
        # freeze for 1/2 second
        self.kicked = True
        Callback(self.unkick, KICKING.length * ANIMATION_LATENCY + 5)

        attack = KickAttack(self, self.opponent_hitbox_ref, self.direction_facing, self.surface_ref, self.game_ref)
        self.game_ref.attacks.append(attack)

        repeat = Repeat(attack.follow_player, 1)
        Callback(repeat.kill, KICKING.length * ANIMATION_LATENCY)

        self.do_animation_and_reset("KICKING")

    def do_animation_and_reset(self, anim):
        self.current_animation = anim
        if (not self.sprite_handler.anims.get(self.current_animation)): return # we have not defined this animation
        self.sprite_handler.update_sprite(self.current_animation)
        Callback(self.go_idle, len(self.sprite_handler.anims[self.current_animation]) * ANIMATION_LATENCY)

    def jump(self):
        if not self.is_jumping:
            self.is_jumping = True
            # JUMP_POWER should be a negative value (e.g., -20) to move up
            self.vertical_velocity = PLAYER_JUMPSPEED 
            self.current_animation = "JUMPING"
            if (not self.sprite_handler.anims.get(self.current_animation)): return
            self.sprite_handler.update_sprite(self.current_animation)

    def fall_through(self):
        is_on_platform = False
        if (self.rect.y < (ground_y - PLAYER_HITBOX_HEIGHT)): 
            self.rect.y += 1 
            for obj in self.game_ref.interactable_game_objects:
                if self.rect.colliderect(obj.rect):
                    is_on_platform = True
                    break
            self.rect.y -= 1 
            
        if is_on_platform and not self.ignoring_platforms:
            self.ignoring_platforms = True
            Callback(self.unignore_platforms, 5)
            
            self.is_jumping = True
            self.vertical_velocity = GRAVITY * 2
            
            self.current_animation = "JUMPING"
            if (self.sprite_handler.anims.get(self.current_animation)): 
                self.sprite_handler.update_sprite(self.current_animation)

    ## FINISH DUCK AND UNUCK
    def duck(self):
        self.is_ducking = True
        self.speed *= 0.5
        self.rect.y += PUNCH_ATTACK_HEIGHT * 1.5
        Callback(self.unduck, 120)

    def unduck(self):
        self.rect.y -= PUNCH_ATTACK_HEIGHT * 1.5
        self.speed /= 0.5
        self.is_ducking = False
    ##

    def damage(self, amount, stun_time):
        self.health -= amount
        print(f"player damaged {amount} hp and now has {self.health} hp left")

        HitNotif(amount, self, self.surface_ref)

        # freeze for stun period
        self.frozen = True
        Callback(self.unfreeze, stun_time)

        self.do_animation_and_reset("FLINCHING")

    def unfreeze(self):
        self.frozen = False
        
    def draw(self):
        self.surface_ref.blit(self.image, self.rect) # draw to screen

PUNCH_ATTACK_WIDTH = 40
PUNCH_ATTACK_HEIGHT = 20
PUNCH_ATTACK_OFFSET_X = -40
PUNCH_ATTACK_OFFSET_Y = 210

class HitNotif(pygame.sprite.Sprite):
    def __init__(self, damage, player, surface):
        super().__init__()
        self.damage = damage
        self.surface_ref = surface
        self.player_ref = player
        self.pos_x = player.rect.x
        self.pos_y = player.rect.y

        self.repeat = Repeat(self.draw, 1)
        Callback(self.kill, 60)

    def move_random(self):
        if (self.player_ref.direction_facing == RIGHT):
            self.pos_x += random.randint(-1, 3)
        else:
            self.pos_x -= random.randint(-1, 3)
        self.pos_y -= random.randint(1, 2)

    def draw(self):
        self.move_random()
        text = font.render(f"{int(self.damage)}", True, RED)
        self.surface_ref.blit(text, (self.pos_x, self.pos_y))

    def kill(self):
        if (self.repeat): self.repeat.kill()
        self.repeat = None
        super().kill()

class PunchAttack(pygame.sprite.Sprite):
    def __init__(self, player, opponent_hitbox, direction, surface, game):
        super().__init__()
        self.image = pygame.Surface((PUNCH_ATTACK_WIDTH, PUNCH_ATTACK_HEIGHT))
        self.image.fill(ORANGE)
        self.player_ref = player
        self.game_ref = game
        self.rect = self.image.get_rect()
        self.surface_ref = surface
        self.opponent_hitbox_ref = opponent_hitbox
        self.flag = True

        if (direction == RIGHT):
            self.rect.center = (self.player_ref.rect.x + PLAYER_SPRITE_WIDTH + PUNCH_ATTACK_OFFSET_X, self.player_ref.rect.y - PLAYER_SPRITE_HEIGHT + PUNCH_ATTACK_OFFSET_Y)
        else:
            self.rect.center = (self.player_ref.rect.x - PUNCH_ATTACK_OFFSET_X, self.player_ref.rect.y - PLAYER_SPRITE_HEIGHT + PUNCH_ATTACK_OFFSET_Y)
        
        Callback(self.delete, 30) # delete attack in 1/2 second
    
    def update(self):
        if (self.rect.colliderect(self.opponent_hitbox_ref.rect) and (self.flag)):
            self.flag = False
            self.opponent_hitbox_ref.player_ref.damage(50, 50)
            self.kill()

        if (DISPLAY_HITBOXES): self.surface_ref.blit(self.image, self.rect) # draw to screen

    def follow_player(self):
        if (self.player_ref.direction_facing == RIGHT):
            self.rect.center = (self.player_ref.rect.x + PLAYER_SPRITE_WIDTH + PUNCH_ATTACK_OFFSET_X, self.player_ref.rect.y - PLAYER_SPRITE_HEIGHT + PUNCH_ATTACK_OFFSET_Y)
        else:
            self.rect.center = (self.player_ref.rect.x - PUNCH_ATTACK_OFFSET_X, self.player_ref.rect.y - PLAYER_SPRITE_HEIGHT + PUNCH_ATTACK_OFFSET_Y)

    def delete(self):
        self.game_ref.attacks.remove(self)
        self.kill()

KICK_ATTACK_WIDTH = 40
KICK_ATTACK_HEIGHT = 20
KICK_ATTACK_OFFSET_X = -40
KICK_ATTACK_OFFSET_Y = 220

class KickAttack(pygame.sprite.Sprite):
    def __init__(self, player, opponent_hitbox, direction, surface, game):
        super().__init__()
        self.image = pygame.Surface((KICK_ATTACK_WIDTH, KICK_ATTACK_HEIGHT))
        self.image.fill(GREEN)
        self.player_ref = player
        self.game_ref = game
        self.rect = self.image.get_rect()
        self.surface_ref = surface
        self.opponent_hitbox_ref = opponent_hitbox
        self.flag = True

        if (direction == RIGHT):
            self.rect.center = (self.player_ref.rect.x + PLAYER_SPRITE_WIDTH + KICK_ATTACK_OFFSET_X, self.player_ref.rect.y - PLAYER_SPRITE_HEIGHT + KICK_ATTACK_OFFSET_Y)
        else:
            self.rect.center = (self.player_ref.rect.x - KICK_ATTACK_OFFSET_X, self.player_ref.rect.y - PLAYER_SPRITE_HEIGHT + KICK_ATTACK_OFFSET_Y)
        
        Callback(self.delete, 30) # delete attack in 1/2 second
    
    def update(self):
        if (self.rect.colliderect(self.opponent_hitbox_ref.rect) and (self.flag)):
            self.flag = False
            self.opponent_hitbox_ref.player_ref.damage(50, 50)
            self.kill()

        if (DISPLAY_HITBOXES): self.surface_ref.blit(self.image, self.rect) # draw to screen

    def follow_player(self):
        if (self.player_ref.direction_facing == RIGHT):
            self.rect.center = (self.player_ref.rect.x + PLAYER_SPRITE_WIDTH + KICK_ATTACK_OFFSET_X, self.player_ref.rect.y - PLAYER_SPRITE_HEIGHT + KICK_ATTACK_OFFSET_Y)
        else:
            self.rect.center = (self.player_ref.rect.x - KICK_ATTACK_OFFSET_X, self.player_ref.rect.y - PLAYER_SPRITE_HEIGHT + KICK_ATTACK_OFFSET_Y)

    def delete(self):
        self.game_ref.attacks.remove(self)
        self.kill()

#region CALLBACKS

class Callback():
    def __init__(self, function, time_in_frames):
        self.function = function
        self.time_in_frames = time_in_frames
        global callbacks
        callbacks.append(self)
    
    def process(self):
        self.time_in_frames -= 1
        if (self.time_in_frames <= 0): self.invoke()

    def invoke(self):
        self.function()
        global callbacks
        callbacks.remove(self)

class Repeat():
    def __init__(self, function, timedelay):
        self.function = function
        self.timedelay = timedelay
        self.timeref = timedelay
        global callbacks
        callbacks.append(self)
    
    def process(self):
        self.timedelay -= 1
        if (self.timedelay <= 0): self.invoke()

    def invoke(self):
        self.function()
        self.timedelay = self.timeref

    def kill(self):
        global callbacks
        callbacks.remove(self)

class Timer():
    def __init__(self, callback_fun, time_in_seconds, game):
        self.callback = callback_fun
        self.time_in_seconds = time_in_seconds
        self.repeat = None
        self.game_ref = game

    def tick(self):
        self.time_in_seconds -= 1

    def start_ticking(self):
        Callback(self.end_action, FPS * self.time_in_seconds)
        self.repeat = Repeat(self.tick, FPS)

    def end_action(self):
        self.callback() # perform action
        if (self.repeat): self.repeat.kill()
        self.time_in_seconds = 0

    def get_time(self):
        return self.time_in_seconds

TOAST_WIDTH = SCREEN_WIDTH / 2
TOAST_HEIGHT = 32 

class Toast(pygame.sprite.Sprite):
    def __init__(self, surface, text, display_time, game, on_kill_callback):
        super().__init__()
        self.image = pygame.Surface((TOAST_WIDTH, TOAST_HEIGHT))
        self.image.fill(GRAY)
        self.rect = self.image.get_rect()
        self.rect.center = (SCREEN_WIDTH / 2, 30)
        self.text = text
        self.surface_ref = surface
        self.display_time = display_time
        self.game_ref = game
        self.on_kill_callback = on_kill_callback

        Callback(self.kill, display_time)

    def draw(self):
        self.surface_ref.blit(self.image, self.rect)
        text = font.render(self.text, True, WHITE)
        self.surface_ref.blit(text, (SCREEN_WIDTH / 2 - 250, 20))

    def kill(self):
        if (self.on_kill_callback): self.on_kill_callback()
        super().kill()

class Button(pygame.sprite.Sprite):
    def __init__(self, surface, on_click, static_sprite, offset, z_layer):
        super().__init__()
        self.image = pygame.image.load(static_sprite.spritesheet).convert_alpha()
        self.rect = self.image.get_rect()
        self.rect.center = offset
        self.surface_ref = surface
        self.on_click = on_click
        self.z = z_layer

        self.is_active = True

    def update(self):
        self.surface_ref.blit(self.image, self.rect)

    def scale(self, multiplier):
        self.image = pygame.transform.scale(self.image, (self.image.get_width() * multiplier, self.image.get_height() * multiplier))

    def change_dimensions(self, new_dimensions):
        self.image = pygame.transform.scale(self.image, new_dimensions)

    def handle_click(self, event):
        if (not self.is_active): return

        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                self.on_click()

class Menu(object):
    def __init__(self):
        self.interactive_elements = []

    def add_button(self, button):
        self.interactive_elements.append(button)
    
    def redraw_frame(self):
        for obj in sorted(self.interactive_elements, key=(lambda x: x.z), reverse=False):
            obj.update()

#endregion

# HEALTHBAR MODIFIABLE ATTRIBUTES

FIRST_HEALTHBAR_OFFSET = (100, 30)
SECOND_HEALTHBAR_OFFSET = (SCREEN_WIDTH - FIRST_HEALTHBAR_OFFSET[0], FIRST_HEALTHBAR_OFFSET[1])
HEALTHBAR_WIDTH = 200
HEALTHBAR_HEIGHT = 20

class HealthBar(pygame.sprite.Sprite):
    def __init__(self, health, surface, offset):
        self.image = pygame.Surface((HEALTHBAR_WIDTH, HEALTHBAR_HEIGHT))
        self.backimage = pygame.Surface((HEALTHBAR_WIDTH, HEALTHBAR_HEIGHT))
        self.image.fill(RED)
        self.backimage.fill(GRAY)

        self.rect = self.image.get_rect()
        self.rect.center = (offset[0], offset[1] + FONT_SIZE * 2)
        
        # attributes
        self.maxhealth = health
        self.surface_ref = surface
        self.offset = offset

    def update(self, label, health):
        text = font.render(label, True, RED)
        self.surface_ref.blit(text, self.offset)
        
        new_barwidth = int((health / self.maxhealth) * HEALTHBAR_WIDTH)
        if (new_barwidth < 0): new_barwidth = 0

        self.image = pygame.Surface((new_barwidth, HEALTHBAR_HEIGHT)) # finish
        self.image.fill(RED)

        self.surface_ref.blit(self.backimage, self.rect)
        self.surface_ref.blit(self.image, self.rect)

class Spritesheet(object):
    def __init__(self, path):
        try:
            self.sheet = pygame.image.load(path).convert_alpha()
        except:
            print(f"Could not locate spritesheet resource: {path} ")
            raise SystemExit
    
    def get_image_at(self, rect):
        crop = pygame.Rect(rect)
        image = pygame.Surface(crop.size, pygame.SRCALPHA).convert_alpha()
        image.blit(self.sheet, (0, 0), crop)
        return image
    
    def load_image_strip(self, rect, image_count):
        rects = []
        for x in range(image_count):
            rects.append((rect[0] + rect[2]*x, rect[1], rect[2], rect[3]))
        images = []
        for rect in rects:
            images.append(self.get_image_at(rect))
        return images

class SpriteHandler(object):
    def __init__(self, player, tickspeed, game):
        self.anims = {}
        self.current_anim = None
        self.current_anim_length = None
        self.current_frame = 0
        self.player_ref = player
        self.tickspeed = tickspeed
        self.game_ref = game
        self.repeat = None
    
    def add_anim(self, name, frames):
        self.anims[name] = frames

    def change_anim(self, new_anim):
        if (self.anims.get(new_anim) == None): return False # if we have not defined this animation, break
        self.current_anim = self.anims[new_anim]
        self.current_frame = 0
        self.current_anim_length = len(self.current_anim)
        return True

    def get_next_frame(self):
        if (self.current_anim != None):
            frame = self.current_anim[self.current_frame % self.current_anim_length]
            self.current_frame += 1
            return frame

    def update_sprite(self, anim):
        if (not self.change_anim(anim)): return # if animation does not exist do nothing
        if (self.repeat): self.repeat.kill()
        self.increment_sprite()
        self.repeat = Repeat(self.increment_sprite, ANIMATION_LATENCY)
    
    def increment_sprite(self):
        new_frame = pygame.transform.scale(self.get_next_frame(), (PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
        if (self.player_ref.direction_facing == LEFT): new_frame = pygame.transform.flip(new_frame, 1, 0)
        self.player_ref.image = new_frame

# GAME OBJECTS

class Platform(pygame.sprite.Sprite):
    def __init__(self, dimensions, location, surface):
        self.image = pygame.Surface(dimensions)
        self.image.fill(ORANGE)
        self.game_ref = None
        self.rect = self.image.get_rect()
        self.surface_ref = surface
        self.rect.center = location
    
    def attach_to_game(self):
        if (not self.game_ref): return # if undefined game do nothing
        self.game_ref.interactable_game_objects.add_internal(self)

    def update(self):
        if (DISPLAY_HITBOXES): self.surface_ref.blit(self.image, self.rect) # draw to screen

    def delete(self):
        if (self.game_ref): self.game_ref.interactable_game_objects.remove_internal(self)
        self.kill()

class StaticSprite(object):
    def __init__(self, name, spritesheet):
        self.name = name
        self.spritesheet = spritesheet

FOREGROUND_OBJECT = 1
BACKGROUND_OBJECT = 2

class SpritedGameObject(pygame.sprite.Sprite):
    def __init__(self, static_sprite, location, surface, z_layer, type):
        super().__init__()
        self.sprite = static_sprite
        self.z = z_layer
        self.type = type

        try:
            self.image = pygame.image.load(self.sprite.spritesheet).convert_alpha()
        except:
            print(f"Could not locate sprite resource: {self.sprite.spritesheet}")
            raise SystemExit

        self.rect = self.image.get_rect()
        self.surface_ref = surface
        self.rect.center = location
        self.game_ref = None
    
    def update(self):
        self.surface_ref.blit(self.image, self.rect) # draw to screen

    def attach_to_game(self):
        if (not self.game_ref): return # if undefined game do nothing
        self.game_ref.static_game_objects.add_internal(self)

    def scale(self, multiplier):
        self.image = pygame.transform.scale(self.image, (self.image.get_width() * multiplier, self.image.get_height() * multiplier))

    def change_dimensions(self, new_dimensions):
        self.image = pygame.transform.scale(self.image, new_dimensions)

    def delete(self):
        self.game_ref.static_game_objects.remove_internal(self)
        self.kill()

class SpritedMenuObject(pygame.sprite.Sprite):
    def __init__(self, static_sprite, location, surface, z_layer, type, menu):
        super().__init__()
        self.sprite = static_sprite
        self.z = z_layer
        self.type = type

        try:
            self.image = pygame.image.load(self.sprite.spritesheet).convert_alpha()
        except:
            print(f"Could not locate sprite resource: {self.sprite.spritesheet}")
            raise SystemExit

        self.rect = self.image.get_rect()
        self.surface_ref = surface
        self.rect.center = location
        self.menu_ref = menu

        self.attach_to_menu()
    
    def update(self):
        self.surface_ref.blit(self.image, self.rect) # draw to screen

    def attach_to_menu(self):
        if (not self.menu_ref): return # if undefined game do nothing
        self.menu_ref.interactive_elements.append(self)

    def scale(self, multiplier):
        self.image = pygame.transform.scale(self.image, (self.image.get_width() * multiplier, self.image.get_height() * multiplier))

    def change_dimensions(self, new_dimensions):
        self.image = pygame.transform.scale(self.image, new_dimensions)

    def delete(self):
        self.menu_ref.interactive_elements.remove(self)
        self.kill()

# GAME

class Map(object):
    def __init__(self, name, interactable_game_objects, static_game_objects, ground_y):
        self.name = name
        self.game_ref = None 
        self.interactable_game_objects = interactable_game_objects
        self.static_game_objects = static_game_objects
        self.ground_y = ground_y

class Game(object):
    def __init__(self, tutorial):
        # FRAME UPDATE REFERENCES
        self.attacks = []
        self.interactable_game_objects = pygame.sprite.Group()
        self.static_game_objects = pygame.sprite.Group()
        self.map_ref = None
        self.tutorial = tutorial
        self.active_toast = None

        # PLAYERS
        self.players = []
        self.player_hitboxes = []
    
    def add_players(self, players, player_hitboxes):
        self.players.extend(players)
        self.player_hitboxes.extend(player_hitboxes)
        for player in self.players:
            player.reset_position()

    def load_map(self, map):
        self.map_ref = map
        map.game_ref = self

        for igo in map.interactable_game_objects:
            igo.game_ref = self
            igo.attach_to_game()
            
        for sgo in map.static_game_objects:
            sgo.game_ref = self
            sgo.attach_to_game()
        
    def redraw_frame(self):

        foreground = []
        background = []

        for obj in self.static_game_objects:
            if (obj.type == FOREGROUND_OBJECT):
                foreground.append(obj)
            else:
                background.append(obj)
        
        # draw in order of z layer

        for obj in sorted(background, key=(lambda x: x.z), reverse=False):
            obj.update()

        for hitbox in self.player_hitboxes:
            hitbox.update()
            if (DISPLAY_HITBOXES): hitbox.draw()

        for player in self.players:
            player.update()
            player.draw()

        for obj in self.interactable_game_objects:
            obj.update()
        
        for attack in self.attacks:
            attack.update()
        
        for obj in sorted(foreground, key=(lambda x: x.z), reverse=False):
            obj.update()

        if (self.tutorial): TUTORIAL.do_tutorial()

        if self.active_toast:
            self.active_toast.draw()

class Tutorial(object):
    def __init__(self, surface, game):
        self.has_moved = False
        self.has_jumped = False
        self.has_punched = False
        self.has_kicked = False
        self.has_dodged = False

        self.surface_ref = surface
        self.game_ref = game
        self.is_toast_active = False

    def toast_finished(self):
        self.is_toast_active = False

    def do_tutorial(self):
        if (self.is_toast_active): return

        toast_text = None
        if (not self.has_moved):
            toast_text = "Use the keys ASD to move around!"
        elif (not self.has_jumped):
            toast_text = "Use the keys W to jump!"
        elif (not self.has_punched):
            toast_text = "Use the J key to punch!"
        elif (not self.has_kicked):
            toast_text = "Use the K key to kick!"
        elif (not self.has_dodged):
            toast_text = "DODGE TUTORIAL"

        if toast_text:
            self.is_toast_active = True
            self.game_ref.active_toast = Toast(self.surface_ref, toast_text, 120, self.game_ref, self.toast_finished)

SWIPE_SPEED = 120

class Screenswipe(pygame.sprite.Sprite):
    def __init__(self, static_sprite, surface):
        super().__init__()
        self.image = pygame.image.load(static_sprite.spritesheet).convert_alpha()
        self.image = pygame.transform.scale(self.image, (SCREEN_WIDTH * 2, SCREEN_HEIGHT))
        self.rect = self.image.get_rect()
        self.rect.center = (SCREEN_WIDTH / 2 + 1600, SCREEN_HEIGHT / 2)
        self.repeat = None
        self.surface_ref = surface

    def update(self):
        self.rect.move_ip(-SWIPE_SPEED, 0)

    def draw(self):
        self.surface_ref.blit(self.image, self.rect)

    def do_effect(self):
        global current_game
        Callback(self.reset, 120)
        self.repeat = Repeat(self.update, 1)

    def reset(self):
        if (self.repeat): self.repeat.kill()
        self.repeat = None
        self.rect.center = (SCREEN_WIDTH / 2 + 1600, SCREEN_HEIGHT / 2)

COUNTDOWN_MAX_SPEED = 60
COUNTDOWN_START_X = SCREEN_WIDTH + 100
COUNTDOWN_CENTER_Y = SCREEN_HEIGHT / 2
COUNTDOWN_DECEL_FRAMES = 20
COUNTDOWN_PAUSE_FRAMES = 20
COUNTDOWN_ACCELERATION_FRAMES = 20

TRANSLUCENT_OVERLAY = "assets/overlay.png"
COUNTDOWN_IMAGES = ["assets/three.png", "assets/two.png", "assets/one.png"]

class Countdown(pygame.sprite.Sprite):
    def __init__(self, surface):
        super().__init__()
        self.current_count = 0
        self.image2 = pygame.image.load(TRANSLUCENT_OVERLAY).convert_alpha()
        self.image2 = pygame.transform.scale(self.image2, (SCREEN_WIDTH, SCREEN_HEIGHT))
        self.image = pygame.image.load(COUNTDOWN_IMAGES[self.current_count]).convert_alpha()
        self.rect = self.image.get_rect()
        self.rect2 = self.image2.get_rect()
        self.rect.center = (COUNTDOWN_START_X, COUNTDOWN_CENTER_Y)
        self.rect2.center = (SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2)
        self.repeat = None
        self.surface_ref = surface
        
        self.state = "IDLE"
        self.frame_count = 0
        self.current_speed = 0

        self.overlay_active = False

    def update(self):
        if self.state == "DECELERATE":
            progress = self.frame_count / COUNTDOWN_DECEL_FRAMES
            self.current_speed = COUNTDOWN_MAX_SPEED * (1 - progress)

            self.rect.move_ip(-self.current_speed, 0)
            self.frame_count += 1

            if self.frame_count >= COUNTDOWN_DECEL_FRAMES:
                self.state = "PAUSE"
                self.frame_count = 0

        elif self.state == "ACCELERATE":
            progress = self.frame_count / COUNTDOWN_ACCELERATION_FRAMES
            self.current_speed = COUNTDOWN_MAX_SPEED * progress # inversely proportional

            self.rect.move_ip(-self.current_speed, 0)
            self.frame_count += 1

            if self.frame_count >= COUNTDOWN_ACCELERATION_FRAMES:
                self.state = "IDLE"
                self.frame_count = 0

        elif self.state == "IDLE":
            pass

    def draw(self):
        if (self.overlay_active): self.surface_ref.blit(self.image2, self.rect2)
        self.surface_ref.blit(self.image, self.rect)

    def do_countdown(self):
        self.do_effect()
        Callback(self.do_effect, 61)
        Callback(self.do_effect, 122)

    def start_accelerate(self):
        self.state = "ACCELERATE"
        self.frame_count = 0

    def do_effect(self):
        if self.current_count < len(COUNTDOWN_IMAGES):
            self.image = pygame.image.load(COUNTDOWN_IMAGES[self.current_count]).convert_alpha()
        
        self.rect.center = (COUNTDOWN_START_X, COUNTDOWN_CENTER_Y)
        self.frame_count = 0
        self.state = "DECELERATE"
        
        if (self.repeat): self.repeat.kill()
        self.repeat = Repeat(self.update, 1)

        Callback(self.start_accelerate, COUNTDOWN_DECEL_FRAMES + COUNTDOWN_PAUSE_FRAMES)
        Callback(self.reset, 60) 

    def reset(self):
        if (self.repeat): self.repeat.kill()
        self.repeat = None
        self.rect.center = (COUNTDOWN_START_X, COUNTDOWN_CENTER_Y)
        self.state = "IDLE"
        self.current_count += 1

SCREENSWIPE = Screenswipe(StaticSprite("SCREENSWIPE", "assets/screen_swipe.png"), screen)
COUNTDOWN = Countdown(screen)

SCREENSWIPE = Screenswipe(StaticSprite("SCREENSWIPE", "assets/screen_swipe.png"), screen)
COUNTDOWN = Countdown(screen)

#region MAIN MENU
MAIN_MENU = Menu()

MAIN_MENU_BACKGROUND = SpritedMenuObject(StaticSprite("MAIN_MENU_BACKGROUND", "assets/main_menu_background.png"), (320, 180), screen, -100, BACKGROUND_OBJECT, MAIN_MENU)
MAIN_MENU_BACKGROUND.change_dimensions((SCREEN_WIDTH, SCREEN_HEIGHT))

def load_tutorial():
    SCREENSWIPE.do_effect()
    Callback(change_game_to_tutorial, 15)

def change_game_to_tutorial():
    global current_menu 
    current_menu = None
    global current_game 
    current_game = TUTORIAL_GAME

def load_mvb():
    SCREENSWIPE.do_effect()
    Callback(change_game_to_mvb, 15)
    Callback(countdown_sequence, 60)
    Callback(disable_countdown_overlay, 243)

def countdown_sequence():
    COUNTDOWN.current_count = 0
    COUNTDOWN.do_countdown()

def disable_countdown_overlay():
    COUNTDOWN.overlay_active = False

def change_game_to_mvb():
    global current_menu 
    current_menu = None
    global current_game 
    current_game = MVB_GAME
    COUNTDOWN.overlay_active = True

MAIN_MENU_TUTORIAL_BUTTON = Button(screen, load_tutorial, StaticSprite("TUTORIAL_BUTTON", "assets/tutorial_button.png"), (SCREEN_WIDTH / 2, 225), 10)
MAIN_MENU_SINGLEPLAYER_BUTTON = Button(screen, load_tutorial, StaticSprite("SINGLEPLAYER_BUTTON", "assets/singleplayer_button.png"), (SCREEN_WIDTH / 2, 300), 10)
MAIN_MENU_MULTIPLAYER_BUTTON = Button(screen, load_mvb, StaticSprite("MULTIPLAYER_BUTTON", "assets/multiplayer_button.png"), (SCREEN_WIDTH / 2, 375), 10)
MAIN_MENU_CHARACTER_BUTTON = Button(screen, load_tutorial, StaticSprite("CHARACTER_BUTTON", "assets/character_menu_button.png"), (SCREEN_WIDTH / 2, 450), 10)

MAIN_MENU.add_button(MAIN_MENU_TUTORIAL_BUTTON)
MAIN_MENU.add_button(MAIN_MENU_SINGLEPLAYER_BUTTON)
MAIN_MENU.add_button(MAIN_MENU_MULTIPLAYER_BUTTON)
MAIN_MENU.add_button(MAIN_MENU_CHARACTER_BUTTON)
#endregion

#region TUTORIAL GAME
TUTORIAL_GAME = Game(True)
TUTORIAL = Tutorial(screen, TUTORIAL_GAME)

MVB_SPAWN_POSITION = PLAYER1_SPAWN_POSITION

TUTORIAL_PLAYER = Player(screen, PLAYER1_KEYLEFT, PLAYER1_KEYRIGHT, PLAYER1_KEYJUMP, PLAYER1_KEYDUCK, PLAYER1_KEYPUNCH, PLAYER1_KEYKICK, MVB_SPAWN_POSITION, RIGHT, FIRST_HEALTHBAR_OFFSET, DEFAULT_CHARACTER, TUTORIAL_GAME, PLAYER_HEALTH, True, TUTORIAL)
HITBOX_TUTORIAL_PLAYER = Hitbox(screen, TUTORIAL_PLAYER)

MVB_DUMMY1_SPAWN_POSITION = (2 * (SCREEN_WIDTH + PLAYER_SPRITE_WIDTH) / 3, 100)
TUTORIAL_DUMMY1 = Player(screen, NO_KEY, NO_KEY, NO_KEY, NO_KEY, NO_KEY, NO_KEY, MVB_DUMMY1_SPAWN_POSITION, RIGHT, (0, 0), DUMMY_CHARACTER, TUTORIAL_GAME, 2147483647, False, None)
HITBOX_TUTORIAL_DUMMY1 = Hitbox(screen, TUTORIAL_DUMMY1)

TUTORIAL_PLAYER.attach_opponent(TUTORIAL_DUMMY1, HITBOX_TUTORIAL_DUMMY1)
TUTORIAL_DUMMY1.attach_opponent(TUTORIAL_PLAYER, HITBOX_TUTORIAL_PLAYER)

TUTORIAL_BACKGROUND = SpritedGameObject(StaticSprite("TUTORIAL_BACKGROUND", "assets/mvb_background.png"), (320, 180), screen, -100, BACKGROUND_OBJECT)
TUTORIAL_BACKGROUND.change_dimensions((SCREEN_WIDTH, SCREEN_HEIGHT))

TUTORIAL_PLATFORM_UPSTAIRS = Platform((SCREEN_WIDTH, 16), (SCREEN_WIDTH / 2, 290), screen)
TUTORIAL_PLATFORM_STAIRS1 = Platform((50, 16), (30, 345), screen)
TUTORIAL_PLATFORM_STAIRS2 = Platform((50, 16), (50, 365), screen)
TUTORIAL_PLATFORM_STAIRS3 = Platform((50, 16), (80, 385), screen)
TUTORIAL_PLATFORM_STAIRS4 = Platform((50, 16), (150, 407), screen)
TUTORIAL_PLATFORM_STAIRS5 = Platform((50, 16), (180, 425), screen)
TUTORIAL_PLATFORM_STAIRS6 = Platform((50, 16), (210, 445), screen)
TUTORIAL_PLATFORM_STAIRS7 = Platform((50, 16), (240, 465), screen)
TUTORIAL_PLATFORM_STAIRS8 = Platform((50, 16), (310, 485), screen)
TUTORIAL_PLATFORM_STAIRS9 = Platform((50, 16), (340, 505), screen)
TUTORIAL_PLATFORM_STAIRS10 = Platform((50, 16), (370, 525), screen)

TUTORIAL_IGO = [TUTORIAL_PLATFORM_UPSTAIRS, TUTORIAL_PLATFORM_STAIRS1, TUTORIAL_PLATFORM_STAIRS2, TUTORIAL_PLATFORM_STAIRS3, TUTORIAL_PLATFORM_STAIRS4, TUTORIAL_PLATFORM_STAIRS5, TUTORIAL_PLATFORM_STAIRS6, TUTORIAL_PLATFORM_STAIRS7, TUTORIAL_PLATFORM_STAIRS8, TUTORIAL_PLATFORM_STAIRS9, TUTORIAL_PLATFORM_STAIRS10]
TUTORIAL_SGO = [TUTORIAL_BACKGROUND]
TUTORIAL_GROUND_Y = 494
ground_y = TUTORIAL_GROUND_Y
TUTORIAL_MAP = Map("TUTORIAL_MAP", TUTORIAL_IGO, TUTORIAL_SGO, TUTORIAL_GROUND_Y)

TUTORIAL_GAME.add_players([TUTORIAL_PLAYER, TUTORIAL_DUMMY1], [HITBOX_TUTORIAL_PLAYER, HITBOX_TUTORIAL_DUMMY1])
TUTORIAL_GAME.load_map(TUTORIAL_MAP)

#endregion

#region MVB_GAME
MVB_GAME = Game(False)

MVB_P1_SPAWN_POSITION = MVB_SPAWN_POSITION
MVB_P2_SPAWN_POSITION = MVB_DUMMY1_SPAWN_POSITION

MVB_PLAYER1 = Player(screen, PLAYER1_KEYLEFT, PLAYER1_KEYRIGHT, PLAYER1_KEYJUMP, PLAYER1_KEYDUCK, PLAYER1_KEYPUNCH, PLAYER1_KEYKICK, MVB_P1_SPAWN_POSITION, RIGHT, FIRST_HEALTHBAR_OFFSET, DEFAULT_CHARACTER, MVB_GAME, PLAYER_HEALTH, True, None)
HITBOX_MVB_PLAYER1 = Hitbox(screen, MVB_PLAYER1)

MVB_PLAYER2 = Player(screen, PLAYER2_KEYLEFT, PLAYER2_KEYRIGHT, PLAYER2_KEYJUMP, PLAYER2_KEYDUCK, PLAYER2_KEYPUNCH, PLAYER2_KEYKICK, MVB_P2_SPAWN_POSITION, LEFT, SECOND_HEALTHBAR_OFFSET, DEFAULT_CHARACTER, MVB_GAME, PLAYER_HEALTH, True, None)
HITBOX_MVB_PLAYER2 = Hitbox(screen, MVB_PLAYER2)

MVB_PLAYER1.attach_opponent(MVB_PLAYER2, HITBOX_MVB_PLAYER2)
MVB_PLAYER2.attach_opponent(MVB_PLAYER1, HITBOX_MVB_PLAYER1)

MVB_IGO = [TUTORIAL_PLATFORM_UPSTAIRS, TUTORIAL_PLATFORM_STAIRS1, TUTORIAL_PLATFORM_STAIRS2, TUTORIAL_PLATFORM_STAIRS3, TUTORIAL_PLATFORM_STAIRS4, TUTORIAL_PLATFORM_STAIRS5, TUTORIAL_PLATFORM_STAIRS6, TUTORIAL_PLATFORM_STAIRS7, TUTORIAL_PLATFORM_STAIRS8, TUTORIAL_PLATFORM_STAIRS9, TUTORIAL_PLATFORM_STAIRS10]
MVB_SGO = [TUTORIAL_BACKGROUND]
MVB_GROUND_Y = 494
ground_y = MVB_GROUND_Y
MVB_MAP = Map("MVB_MAP", MVB_IGO, MVB_SGO, MVB_GROUND_Y)

MVB_GAME.add_players([MVB_PLAYER1, MVB_PLAYER2], [HITBOX_MVB_PLAYER1, HITBOX_MVB_PLAYER2])
MVB_GAME.load_map(MVB_MAP)
#endregion

#region TEST_GAME

# TESTING GAME

'''
PLAYER1 = Player(screen, PLAYER1_KEYLEFT, PLAYER1_KEYRIGHT, PLAYER1_KEYJUMP, PLAYER1_KEYDUCK, PLAYER1_KEYPUNCH, PLAYER1_KEYKICK, PLAYER1_SPAWN_POSITION, RIGHT, FIRST_HEALTHBAR_OFFSET, DEFAULT_CHARACTER, GAME)
HITBOX_PLAYER1 = Hitbox(screen, PLAYER1)

PLAYER2 = Player(screen, PLAYER2_KEYLEFT, PLAYER2_KEYRIGHT, PLAYER2_KEYJUMP, PLAYER2_KEYDUCK, PLAYER2_KEYPUNCH, PLAYER2_KEYKICK, PLAYER2_SPAWN_POSITION, LEFT, SECOND_HEALTHBAR_OFFSET, DEFAULT_CHARACTER, GAME)
HITBOX_PLAYER2 = Hitbox(screen, PLAYER2)

PLAYER1.attach_opponent(PLAYER2, HITBOX_PLAYER2)
PLAYER2.attach_opponent(PLAYER1, HITBOX_PLAYER1)
'''

## GAME OBJECTS

'''
# platforms add themselves automatically to game
plat = Platform((196 * 2, 16), (480, 300), screen)
plat_sprite = SpritedGameObject(StaticSprite("PLATFORM", "assets/platform.png"), (350, 300), screen, 10, FOREGROUND_OBJECT)
plat_sprite.scale(2)
background = SpritedGameObject(StaticSprite("BACKGROUND", "assets/background.png"), (320, 180), screen, -100, BACKGROUND_OBJECT)
background.change_dimensions((SCREEN_WIDTH, SCREEN_HEIGHT))

TESTING_IGO = [plat]
TESTING_SGO = [plat_sprite, background]
TESTING_MAP = Map("TESTING_MAP", TESTING_IGO, TESTING_SGO)

GAME.load_map(TESTING_MAP)

# ADD DEFINITIONS TO GAME

GAME.add_players([PLAYER1, PLAYER2], [HITBOX_PLAYER1, HITBOX_PLAYER2])
'''

#endregion

#region FRAMELOOP

current_menu = MAIN_MENU

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            exit()

        if (current_menu):
            for element in current_menu.interactive_elements:
                if isinstance(element, Button):
                    element.handle_click(event)

    # game code
    screen.fill(WHITE)

    # debug
    # current_game = TUTORIAL_GAME
    #

    if (current_menu):
        current_menu.redraw_frame()
    elif (current_game):
        current_game.redraw_frame()

    for callback in callbacks:
            callback.process()

    SCREENSWIPE.draw()
    COUNTDOWN.draw()

    pygame.display.update()
    clock.tick(FPS)

#endregion FRAMELOOP